"""Tests for role-based permissions."""
import pytest
from app.models.membership import MembershipRole
from app.services import permission_service
from .conftest import create_user, create_tenant, add_member


class TestRolePermissions:
    """Verify the permission matrix for each role."""

    def _setup_member(self, db, tenant, role):
        user = create_user(
            email=f"{role.value}_user_{id(tenant)}@example.com",
            name=f"{role.value.capitalize()} User",
        )
        add_member(tenant, user, role)
        return user

    def test_owner_has_all_permissions(self, db, user_a, tenant_a):
        permissions_to_check = [
            "workspace.view", "workspace.update",
            "content.create", "content.approve", "content.publish",
            "members.invite", "members.remove",
            "billing.view", "billing.manage",
            "social_accounts.connect",
        ]
        for perm in permissions_to_check:
            assert permission_service.has_permission(user_a.id, tenant_a.id, perm) is True, \
                f"Owner should have: {perm}"

    def test_editor_can_create_not_approve(self, db, tenant_a):
        editor = self._setup_member(db, tenant_a, MembershipRole.EDITOR)
        assert permission_service.has_permission(editor.id, tenant_a.id, "content.create") is True
        assert permission_service.has_permission(editor.id, tenant_a.id, "content.edit") is True
        assert permission_service.has_permission(editor.id, tenant_a.id, "content.approve") is False
        assert permission_service.has_permission(editor.id, tenant_a.id, "content.publish") is False
        assert permission_service.has_permission(editor.id, tenant_a.id, "billing.manage") is False
        assert permission_service.has_permission(editor.id, tenant_a.id, "members.invite") is False

    def test_publisher_can_approve_not_create(self, db, tenant_a):
        publisher = self._setup_member(db, tenant_a, MembershipRole.PUBLISHER)
        assert permission_service.has_permission(publisher.id, tenant_a.id, "content.approve") is True
        assert permission_service.has_permission(publisher.id, tenant_a.id, "content.publish") is True
        assert permission_service.has_permission(publisher.id, tenant_a.id, "content.create") is False
        assert permission_service.has_permission(publisher.id, tenant_a.id, "content.generate") is False
        assert permission_service.has_permission(publisher.id, tenant_a.id, "billing.manage") is False

    def test_admin_cannot_manage_billing(self, db, tenant_a):
        admin = self._setup_member(db, tenant_a, MembershipRole.ADMIN)
        assert permission_service.has_permission(admin.id, tenant_a.id, "members.invite") is True
        assert permission_service.has_permission(admin.id, tenant_a.id, "content.approve") is True
        assert permission_service.has_permission(admin.id, tenant_a.id, "billing.manage") is False

    def test_inactive_user_has_no_permissions(self, db, tenant_a):
        user = create_user(email="inactive@example.com", name="Inactive User")
        assert permission_service.has_permission(user.id, tenant_a.id, "content.view") is False

    def test_can_manage_role_hierarchy(self, db):
        assert permission_service.user_can_manage_role(MembershipRole.OWNER, MembershipRole.ADMIN) is True
        assert permission_service.user_can_manage_role(MembershipRole.OWNER, MembershipRole.EDITOR) is True
        assert permission_service.user_can_manage_role(MembershipRole.ADMIN, MembershipRole.EDITOR) is True
        assert permission_service.user_can_manage_role(MembershipRole.ADMIN, MembershipRole.PUBLISHER) is True
        assert permission_service.user_can_manage_role(MembershipRole.ADMIN, MembershipRole.OWNER) is False
        assert permission_service.user_can_manage_role(MembershipRole.EDITOR, MembershipRole.PUBLISHER) is False


class TestInvitationFlow:
    def test_invite_creates_pending_invitation(self, db, user_a, tenant_a):
        from app.services.tenant_service import invite_member
        invitation, error = invite_member(
            tenant_id=tenant_a.id,
            email="invited@example.com",
            role=MembershipRole.EDITOR,
            invited_by_id=user_a.id,
        )
        assert error is None
        assert invitation is not None
        assert invitation.is_pending is True
        assert invitation.email == "invited@example.com"

    def test_duplicate_invite_fails(self, db, user_a, tenant_a):
        from app.services.tenant_service import invite_member
        invite_member(
            tenant_id=tenant_a.id,
            email="dup@example.com",
            role=MembershipRole.EDITOR,
            invited_by_id=user_a.id,
        )
        _, error = invite_member(
            tenant_id=tenant_a.id,
            email="dup@example.com",
            role=MembershipRole.EDITOR,
            invited_by_id=user_a.id,
        )
        assert error is not None

    def test_accept_invitation_creates_membership(self, db, user_a, tenant_a):
        from app.services.tenant_service import invite_member, accept_invitation
        invited_user = create_user(email="accept_test@example.com", name="Accept User")

        invitation, _ = invite_member(
            tenant_id=tenant_a.id,
            email="accept_test@example.com",
            role=MembershipRole.EDITOR,
            invited_by_id=user_a.id,
        )

        success, result = accept_invitation(invitation.raw_token, invited_user.id)
        assert success is True

        membership = permission_service.get_membership(invited_user.id, tenant_a.id)
        assert membership is not None
        assert membership.role == MembershipRole.EDITOR

