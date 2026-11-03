"""Tenant service — workspace creation, membership and invitation management."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.tenant import Tenant, TenantStatus
from ..models.membership import TenantMembership, MembershipRole, MembershipStatus
from ..models.invitation import Invitation
from ..models.plan import Plan, PlanTier
from ..models.subscription import Subscription, SubscriptionStatus
from ..models.audit_log import AuditLog

logger = structlog.get_logger(__name__)

INVITATION_TTL_DAYS = 7


def _slug_from_name(name: str) -> str:
    """Convert a workspace name to a URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:80] or "workspace"


def _unique_slug(base: str) -> str:
    """Ensure slug is unique by appending a random suffix if needed."""
    slug = base
    for _ in range(10):
        existing = Tenant.query.filter_by(slug=slug).first()
        if not existing:
            return slug
        slug = f"{base}-{secrets.token_hex(3)}"
    raise RuntimeError("Could not generate unique slug")


def create_tenant(name: str, owner_user_id: str) -> tuple[Optional[Tenant], Optional[str]]:
    """Create a new tenant workspace and assign the creator as Owner.

    Also creates a default free subscription for the tenant.

    Returns:
        Tuple of (tenant, error_message).
    """
    name = name.strip()
    if not name:
        return None, "Workspace name is required."

    slug = _unique_slug(_slug_from_name(name))

    free_plan = Plan.query.filter_by(tier=PlanTier.FREE).first()

    tenant = Tenant(name=name, slug=slug)
    db.session.add(tenant)
    db.session.flush()

    membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=owner_user_id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    db.session.add(membership)

    if free_plan:
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.TRIALING,
        )
        db.session.add(subscription)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, "A workspace with this name already exists."

    _audit(
        action="tenant.created",
        tenant_id=tenant.id,
        user_id=owner_user_id,
        details={"name": name, "slug": slug},
    )

    logger.info("tenant_created", tenant_id=tenant.id, slug=slug, owner=owner_user_id)
    return tenant, None


def get_user_tenants(user_id: str) -> list[Tenant]:
    """Return all active tenants accessible by a user."""
    memberships = (
        TenantMembership.query
        .filter_by(user_id=user_id, status=MembershipStatus.ACTIVE)
        .all()
    )
    tenant_ids = [m.tenant_id for m in memberships]
    if not tenant_ids:
        return []
    return (
        Tenant.query
        .filter(Tenant.id.in_(tenant_ids), Tenant.status == TenantStatus.ACTIVE)
        .order_by(Tenant.name)
        .all()
    )


def get_membership(user_id: str, tenant_id: str) -> Optional[TenantMembership]:
    """Return the active membership for a user in a tenant, or None."""
    return TenantMembership.query.filter_by(
        user_id=user_id,
        tenant_id=tenant_id,
        status=MembershipStatus.ACTIVE,
    ).first()


def invite_member(
    tenant_id: str,
    email: str,
    role: MembershipRole,
    invited_by_id: str,
) -> tuple[Optional[Invitation], Optional[str]]:
    """Create and return a pending invitation.

    Returns (invitation, error_message). The raw token for the email
    is available as invitation.raw_token (transient attribute).
    """
    email = email.lower().strip()

    from ..models.user import User
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        existing_membership = get_membership(existing_user.id, tenant_id)
        if existing_membership:
            return None, "This person is already a member of the workspace."

    existing_inv = (
        Invitation.query
        .filter_by(tenant_id=tenant_id, email=email)
        .filter(Invitation.accepted_at.is_(None))
        .first()
    )

    if existing_inv and existing_inv.is_pending:
        return None, "A pending invitation already exists for this email address."

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    invitation = Invitation(
        tenant_id=tenant_id,
        email=email,
        role=role,
        token_hash=token_hash,
        invited_by_id=invited_by_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_TTL_DAYS),
    )
    db.session.add(invitation)
    db.session.commit()

    invitation.raw_token = raw_token

    _audit(
        action="tenant.member_invited",
        tenant_id=tenant_id,
        user_id=invited_by_id,
        details={"invited_email": email, "role": role.value},
    )

    return invitation, None


def accept_invitation(token: str, user_id: str) -> tuple[bool, str]:
    """Accept a workspace invitation.

    Returns (success, tenant_id_or_error_message).
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invitation = Invitation.query.filter_by(token_hash=token_hash).first()

    if not invitation:
        return False, "Invalid invitation link."
    if not invitation.is_pending:
        return False, "This invitation has already been used or has expired."

    from ..models.user import User
    user = db.session.get(User, user_id)
    if not user or user.email.lower() != invitation.email.lower():
        return False, "This invitation is for a different email address."

    membership = TenantMembership(
        tenant_id=invitation.tenant_id,
        user_id=user_id,
        role=invitation.role,
        status=MembershipStatus.ACTIVE,
    )
    db.session.add(membership)

    invitation.accepted_at = datetime.now(timezone.utc)
    db.session.commit()

    _audit(
        action="tenant.invitation_accepted",
        tenant_id=invitation.tenant_id,
        user_id=user_id,
        details={"email": invitation.email, "role": invitation.role.value},
    )

    return True, invitation.tenant_id


def update_tenant_settings(
    tenant_id: str,
    user_id: str,
    **kwargs
) -> tuple[bool, Optional[str]]:
    """Update tenant settings (name, timezone, brand fields)."""
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return False, "Workspace not found."

    allowed_fields = {
        "name", "timezone", "brand_name", "brand_description",
        "brand_voice", "logo_url", "website_url"
    }

    for field, value in kwargs.items():
        if field in allowed_fields:
            setattr(tenant, field, value)

    db.session.commit()

    _audit(
        action="tenant.settings_updated",
        tenant_id=tenant_id,
        user_id=user_id,
        details={"fields": list(kwargs.keys())},
    )

    return True, None


def get_tenant_members(tenant_id: str) -> list[TenantMembership]:
    """Return all active members of a tenant."""
    return (
        TenantMembership.query
        .filter_by(tenant_id=tenant_id, status=MembershipStatus.ACTIVE)
        .all()
    )


def remove_member(
    tenant_id: str,
    target_user_id: str,
    requesting_user_id: str,
) -> tuple[bool, Optional[str]]:
    """Remove a member from a tenant."""
    membership = TenantMembership.query.filter_by(
        tenant_id=tenant_id,
        user_id=target_user_id,
        status=MembershipStatus.ACTIVE,
    ).first()

    if not membership:
        return False, "Member not found."

    if membership.role == MembershipRole.OWNER:
        owner_count = TenantMembership.query.filter_by(
            tenant_id=tenant_id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        ).count()
        if owner_count <= 1:
            return False, "Cannot remove the only workspace owner."

    membership.status = MembershipStatus.REMOVED
    db.session.commit()

    _audit(
        action="tenant.member_removed",
        tenant_id=tenant_id,
        user_id=requesting_user_id,
        details={"removed_user_id": target_user_id},
    )

    return True, None


def _audit(
    action: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[dict] = None
) -> None:
    """Write an audit log entry."""
    try:
        log = AuditLog(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            details_json=details,
        )
        db.session.add(log)
        db.session.flush()
    except Exception as exc:
        logger.warning("audit_log_failed", action=action, error=str(exc))
