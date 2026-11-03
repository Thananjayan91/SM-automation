"""Critical tests: verify that tenants cannot access each other's data.

These tests are the acceptance criteria for Milestone 1.
A failure here means the multi-tenant foundation is broken.
"""
import pytest
from app.models.membership import MembershipRole
from app.services import permission_service
from .conftest import create_user, create_tenant, add_member


class TestTenantIsolation:
    """A user from Tenant A must not access Tenant B's data."""

    def test_user_a_cannot_access_tenant_b(self, db, user_a, tenant_a, user_b, tenant_b):
        """User A has no membership in Tenant B."""
        membership = permission_service.get_membership(user_a.id, tenant_b.id)
        assert membership is None

    def test_user_b_cannot_access_tenant_a(self, db, user_a, tenant_a, user_b, tenant_b):
        """User B has no membership in Tenant A."""
        membership = permission_service.get_membership(user_b.id, tenant_a.id)
        assert membership is None

    def test_has_permission_returns_false_for_wrong_tenant(self, db, user_a, tenant_a, user_b, tenant_b):
        """has_permission returns False when user is not in that tenant."""
        # user_a is owner of tenant_a — but has no access to tenant_b
        assert permission_service.has_permission(user_a.id, tenant_b.id, "content.view") is False
        assert permission_service.has_permission(user_b.id, tenant_a.id, "content.view") is False

    def test_tenant_a_owner_has_full_permissions_in_tenant_a(self, db, user_a, tenant_a):
        """The workspace owner has all permissions in their own tenant."""
        assert permission_service.has_permission(user_a.id, tenant_a.id, "content.view") is True
        assert permission_service.has_permission(user_a.id, tenant_a.id, "content.approve") is True
        assert permission_service.has_permission(user_a.id, tenant_a.id, "billing.manage") is True
        assert permission_service.has_permission(user_a.id, tenant_a.id, "members.invite") is True

    def test_require_permission_raises_for_wrong_tenant(self, db, user_a, tenant_b, app):
        """require_permission raises PermissionError for cross-tenant access."""
        with app.app_context():
            with pytest.raises(PermissionError):
                permission_service.require_permission(user_a.id, tenant_b.id, "content.view")

    def test_api_get_tenant_rejects_wrong_user(self, client, db, user_a, tenant_a, user_b, tenant_b):
        """API: user_b cannot retrieve tenant_a details."""
        # Login as user_b
        client.post(
            "/auth/login",
            data={"email": "user_b@example.com", "password": "Test1234!"},
            follow_redirects=True,
        )
        response = client.get(f"/api/v1/tenants/{tenant_a.id}")
        assert response.status_code == 404  # Not 403 to avoid leaking tenant existence

    def test_api_get_tenant_allows_own_tenant(self, client, db, user_a, tenant_a):
        """API: user_a can retrieve their own tenant details."""
        client.post(
            "/auth/login",
            data={"email": "user_a@example.com", "password": "Test1234!"},
            follow_redirects=True,
        )
        response = client.get(f"/api/v1/tenants/{tenant_a.id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == tenant_a.id

    def test_shared_user_only_sees_own_tenants(self, db, user_a, tenant_a, tenant_b):
        """A user who belongs to only one tenant does not see the other."""
        from app.services.tenant_service import get_user_tenants
        tenants_for_a = get_user_tenants(user_a.id)
        ids = [t.id for t in tenants_for_a]
        assert tenant_a.id in ids
        assert tenant_b.id not in ids

    def test_multi_tenant_user_sees_both_tenants(self, db, user_a, tenant_a, tenant_b):
        """A user with membership in both tenants sees both."""
        add_member(tenant_b, user_a, MembershipRole.EDITOR)
        from app.services.tenant_service import get_user_tenants
        tenants_for_a = get_user_tenants(user_a.id)
        ids = [t.id for t in tenants_for_a]
        assert tenant_a.id in ids
        assert tenant_b.id in ids


class TestTenantCreation:
    def test_create_tenant_assigns_owner(self, db, user_a):
        from app.services.tenant_service import create_tenant as svc_create_tenant, get_membership
        tenant, error = svc_create_tenant("My New Workspace", user_a.id)
        assert error is None
        assert tenant is not None
        membership = get_membership(user_a.id, tenant.id)
        assert membership is not None
        assert membership.role == MembershipRole.OWNER

    def test_create_tenant_creates_slug(self, db, user_a):
        from app.services.tenant_service import create_tenant as svc_create_tenant
        tenant, _ = svc_create_tenant("Slug Test Workspace", user_a.id)
        assert tenant.slug is not None
        assert " " not in tenant.slug
        assert tenant.slug == tenant.slug.lower()
