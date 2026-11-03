"""pytest configuration and shared fixtures for the test suite."""
import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.models.tenant import Tenant
from app.models.membership import TenantMembership, MembershipRole, MembershipStatus
from app.models.plan import Plan, PlanTier


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        _seed_plans()
        yield application
        _db.drop_all()


def _seed_plans():
    """Create test plan records."""
    if Plan.query.filter_by(tier=PlanTier.FREE).first():
        return
    plans = [
        Plan(
            name="Free",
            tier=PlanTier.FREE,
            max_social_accounts=1,
            max_team_members=1,
            max_ai_generations_per_month=20,
            max_image_generations_per_month=5,
            audit_history_days=7,
        ),
        Plan(
            name="Starter",
            tier=PlanTier.STARTER,
            price_monthly_cents=2900,
            max_social_accounts=3,
            max_team_members=2,
            max_ai_generations_per_month=200,
            max_image_generations_per_month=50,
            audit_history_days=90,
        ),
        Plan(
            name="Pro",
            tier=PlanTier.PRO,
            price_monthly_cents=9900,
            max_social_accounts=10,
            max_team_members=5,
            max_ai_generations_per_month=1000,
            max_image_generations_per_month=250,
            audit_history_days=365,
        ),
    ]
    for p in plans:
        _db.session.add(p)
    _db.session.commit()


@pytest.fixture(scope="function")
def db(app):
    """Provide a clean database for each test."""
    with app.app_context():
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            if table.name != "plans":
                _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture(scope="function")
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def runner(app):
    """Flask CLI test runner."""
    return app.test_cli_runner()


# ── User helpers ──────────────────────────────────────────────────────────────

def create_user(email: str = "test@example.com", password: str = "Test1234!", name: str = "Test User") -> User:
    """Create and persist a test user."""
    user = User(email=email, name=name)
    user.set_password(password)
    _db.session.add(user)
    _db.session.flush()
    return user


def create_tenant(name: str = "Test Workspace", owner: User = None) -> Tenant:
    """Create and persist a test tenant with an optional owner membership."""
    from app.services.tenant_service import _unique_slug, _slug_from_name
    slug = _unique_slug(_slug_from_name(name))
    tenant = Tenant(name=name, slug=slug)
    _db.session.add(tenant)
    _db.session.flush()

    if owner:
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        _db.session.add(membership)
        _db.session.flush()

    return tenant


def add_member(tenant: Tenant, user: User, role: MembershipRole) -> TenantMembership:
    """Add a user as a member of a tenant."""
    membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    _db.session.add(membership)
    _db.session.flush()
    return membership


@pytest.fixture
def user_a(db):
    """A regular test user."""
    return create_user(email="user_a@example.com", name="User A")


@pytest.fixture
def user_b(db):
    """A second test user — belongs to a separate tenant."""
    return create_user(email="user_b@example.com", name="User B")


@pytest.fixture
def tenant_a(db, user_a):
    """Tenant A owned by user_a."""
    return create_tenant("Tenant A", owner=user_a)


@pytest.fixture
def tenant_b(db, user_b):
    """Tenant B owned by user_b."""
    return create_tenant("Tenant B", owner=user_b)


def login(client, email: str, password: str):
    """Log in a user via the web form and return the response."""
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
