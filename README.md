# AI Social Publisher SaaS

Multi-tenant social media content creation, AI-assisted generation, approval and publishing platform.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Web frontend | Flask + Jinja2 + HTMX + Bootstrap 5 |
| Mobile app | React Native + Expo + TypeScript |
| Backend API | Python 3.12+ + Flask + SQLAlchemy 2.x |
| Database | PostgreSQL |
| Background jobs | Celery + Redis |
| Media storage | S3-compatible object storage |
| Deployment | AWS EC2 + Nginx + Gunicorn |

## Repository structure

```
ai-social-saas/
├── backend/              # Flask application + REST API
│   ├── app/
│   │   ├── auth/         # Authentication blueprint
│   │   ├── tenants/      # Workspace management blueprint
│   │   ├── web/          # Web application views
│   │   ├── api/v1/       # REST API (mobile + integrations)
│   │   ├── models/       # SQLAlchemy models
│   │   ├── services/     # Business logic
│   │   ├── tasks/        # Celery background tasks
│   │   ├── templates/    # Jinja2 HTML templates
│   │   └── static/       # CSS, JS, images
│   ├── migrations/       # Alembic database migrations
│   ├── tests/            # pytest test suite
│   ├── config.py         # Configuration classes
│   ├── wsgi.py           # WSGI entry point
│   ├── worker.py         # Celery worker entry point
│   └── requirements.txt  # Pinned dependencies
├── mobile/               # React Native + Expo app (Milestone 6)
├── deployment/           # Nginx, systemd, scripts
├── docs/                 # Architecture and API documentation
└── README.md
```

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Flask foundation, PostgreSQL, auth, multi-tenant, roles, responsive dashboard | ✅ Complete |
| 2 | Source submission, media uploads, draft management, post editor | ✅ Complete |
| 3 | Background jobs, research, AI text generation, image generation | 🔜 Next |
| 4 | Versioned approval, Facebook Page publishing | ⏳ Planned |
| 5 | Instagram publishing, independent target states | ⏳ Planned |
| 6 | Android app (React Native + Expo) | ⏳ Planned |
| 7 | Usage limits, billing, SaaS admin, production hardening | ⏳ Planned |

## Quick start (development)

### Prerequisites

- Python 3.10+ (Python 3.12 recommended)
- PostgreSQL 15+
- Redis 7+

### Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your database URL, secret key, etc.

# 5. Create database
createdb ai_social_publisher

# 6. Run database migrations
flask db upgrade

# 7. Seed initial plan data (optional, run once)
flask shell
>>> from app.extensions import db
>>> from app.models.plan import Plan, PlanTier
>>> db.session.add(Plan(name="Free", tier=PlanTier.FREE, max_social_accounts=1, max_team_members=1, max_ai_generations_per_month=20, max_image_generations_per_month=5, audit_history_days=7))
>>> db.session.commit()
>>> exit()

# 8. Run the development server
flask run
```

Open http://localhost:5000/auth/register to create your first account and workspace.

### Running tests

```bash
cd backend

# Run the test suite
pytest

# Run tenant isolation acceptance tests
pytest tests/test_tenant_isolation.py -v
```

### Milestone 1 acceptance test

```
Two tenants cannot access each other's records.
```

Run: `pytest tests/test_tenant_isolation.py -v`

## Deployment on Render.com

The repository includes a ready-to-use Render Blueprint (`render.yaml`).
1. Connect this GitHub repository on [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** -> **Blueprint**.
3. Render automatically provisions the Flask Web Service, Celery Background Worker, PostgreSQL, and Redis.
4. See [`docs/render_deployment.md`](docs/render_deployment.md) for full instructions and free-tier options.

## Key environment variables

See `backend/.env.example` for all required environment variables.
- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — Flask secret key
- `REDIS_URL` — Redis connection string
- `CREDENTIAL_ENCRYPTION_KEY` — Fernet key for encrypting OAuth tokens
