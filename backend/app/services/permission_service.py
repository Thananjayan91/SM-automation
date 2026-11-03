"""Permission service — centralised authorization checks.

All permission decisions must go through this module. Do not scatter
role checks across templates, route handlers, or API endpoints.
The only source of truth for tenant context is the authenticated
user's active TenantMembership.
"""
from typing import Optional

from ..models.membership import TenantMembership, MembershipRole, MembershipStatus

_PERMISSIONS: dict[MembershipRole, set[str]] = {
    MembershipRole.OWNER: {
        # Workspace management
        "workspace.view",
        "workspace.update",
        "workspace.delete",
        # Member management
        "members.view",
        "members.invite",
        "members.remove",
        "members.change_role",
        # Social accounts
        "social_accounts.view",
        "social_accounts.connect",
        "social_accounts.disconnect",
        # Content
        "content.create",
        "content.edit",
        "content.delete",
        "content.generate",
        "content.approve",
        "content.publish",
        "content.view",
        # Media
        "media.upload",
        "media.delete",
        "media.view",
        # Analytics
        "analytics.view",
        # Settings
        "settings.view",
        "settings.update",
        # Billing
        "billing.view",
        "billing.manage",
        # AI settings
        "ai_settings.view",
        "ai_settings.update",
    },
    MembershipRole.ADMIN: {
        "workspace.view",
        "workspace.update",
        "members.view",
        "members.invite",
        "members.remove",
        "social_accounts.view",
        "social_accounts.connect",
        "social_accounts.disconnect",
        "content.create",
        "content.edit",
        "content.delete",
        "content.generate",
        "content.approve",
        "content.publish",
        "content.view",
        "media.upload",
        "media.delete",
        "media.view",
        "analytics.view",
        "settings.view",
        "settings.update",
        "ai_settings.view",
        "ai_settings.update",
    },
    MembershipRole.EDITOR: {
        "workspace.view",
        "content.create",
        "content.edit",
        "content.generate",
        "content.view",
        "media.upload",
        "media.view",
        "analytics.view",
        "settings.view",
    },
    MembershipRole.PUBLISHER: {
        "workspace.view",
        "content.view",
        "content.approve",
        "content.publish",
        "media.view",
        "analytics.view",
        "settings.view",
    },
}


def get_membership(user_id: str, tenant_id: str) -> Optional[TenantMembership]:
    """Retrieve a user's active membership for a tenant."""
    return TenantMembership.query.filter_by(
        user_id=user_id,
        tenant_id=tenant_id,
        status=MembershipStatus.ACTIVE,
    ).first()


def has_permission(user_id: str, tenant_id: str, permission: str) -> bool:
    """Check if a user has a given permission in a tenant."""
    membership = get_membership(user_id, tenant_id)
    if not membership:
        return False
    return permission in _PERMISSIONS.get(membership.role, set())


def require_permission(user_id: str, tenant_id: str, permission: str) -> None:
    """Assert that a user has a permission, raising PermissionError if not."""
    if not has_permission(user_id, tenant_id, permission):
        raise PermissionError(
            f"User {user_id} does not have '{permission}' in tenant {tenant_id}"
        )


def get_user_role(user_id: str, tenant_id: str) -> Optional[MembershipRole]:
    """Return the user's role in the tenant, or None if not a member."""
    membership = get_membership(user_id, tenant_id)
    return membership.role if membership else None


def user_can_manage_role(actor_role: MembershipRole, target_role: MembershipRole) -> bool:
    """Check if one role can assign or manage another role."""
    if actor_role == MembershipRole.OWNER:
        return True
    if actor_role == MembershipRole.ADMIN:
        return target_role in {MembershipRole.EDITOR, MembershipRole.PUBLISHER}
    return False

