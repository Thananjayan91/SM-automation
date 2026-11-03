# REST API Reference

**Base URL:** `/api/v1`

**Authentication:** Cookie-based session (web) or Bearer token (mobile, Milestone 6)

**Response format:** JSON

**Pagination:** List endpoints accept `?page=1&per_page=20`

**Error format:**
```json
{
  "error": "error_code",
  "message": "Human-readable description"
}
```

## Authentication

### POST /api/v1/auth/register
Register a new account.

**Body:**
```json
{
  "email": "user@example.com",
  "password": "Password123!",
  "name": "Alex Smith"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "Alex Smith",
  "created_at": "2026-10-20T12:00:00Z"
}
```

### POST /api/v1/auth/login
Authenticate and establish a session.

**Body:**
```json
{
  "email": "user@example.com",
  "password": "Password123!"
}
```

**Response 200:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "Alex Smith"
  },
  "tenants": [
    {
      "id": "uuid",
      "name": "Acme Brand",
      "slug": "acme-brand"
    }
  ]
}
```

### POST /api/v1/auth/logout
Revoke the current session.

**Response 200:**
```json
{
  "message": "Logged out successfully"
}
```

### POST /api/v1/auth/forgot-password
Request a password reset email. Always returns 200 to prevent email enumeration.

**Body:**
```json
{
  "email": "user@example.com"
}
```

**Response 200:**
```json
{
  "message": "If an account exists for this email, a reset link has been sent."
}
```

### GET /api/v1/me
Return current authenticated user and accessible workspace memberships.

**Response 200:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "Alex Smith",
    "is_platform_admin": false
  },
  "tenants": [
    {
      "id": "uuid",
      "name": "Acme Brand",
      "slug": "acme-brand"
    }
  ]
}
```

## Workspaces (Tenants)

### GET /api/v1/tenants
List all workspaces accessible to the authenticated user.

### POST /api/v1/tenants
Create a new workspace. The authenticated user becomes Owner.

**Body:**
```json
{
  "name": "My Brand"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "name": "My Brand",
  "slug": "my-brand",
  "timezone": "UTC"
}
```

### GET /api/v1/tenants/{tenant_id}
Get workspace details. Returns 404 if the user is not an active member.

### GET /api/v1/tenants/{tenant_id}/members
List active members in the workspace. Requires `members.view` permission.

### POST /api/v1/tenants/{tenant_id}/invitations
Invite a new member to the workspace. Requires `members.invite` permission.

**Body:**
```json
{
  "email": "colleague@example.com",
  "role": "editor"
}
```

---

## Planned Endpoints (Milestones 2–7)

### Content Endpoints (Milestone 2–3)
- `POST /api/v1/sources` — Submit URL or topic
- `GET /api/v1/sources/{id}` — Get source status
- `POST /api/v1/sources/{id}/research` — Run background research
- `GET /api/v1/research-runs/{id}` — Get research results
- `POST /api/v1/media/uploads` — Upload media asset
- `GET /api/v1/media` — List tenant media assets
- `POST /api/v1/posts/generate` — Trigger asynchronous AI generation
- `GET /api/v1/jobs/{id}` — Check Celery job progress
- `GET /api/v1/posts` — Search and filter posts
- `GET /api/v1/posts/{id}` — Retrieve post with target states
- `PATCH /api/v1/posts/{id}` — Edit draft content
- `POST /api/v1/posts/{id}/approve` — Approve immutable PostVersion

### Publishing Endpoints (Milestone 4–5)
- `GET /api/v1/integrations/meta/connect` — Begin Meta OAuth flow
- `GET /api/v1/integrations/meta/callback` — Meta OAuth callback
- `GET /api/v1/social-accounts` — List connected accounts
- `POST /api/v1/social-accounts/{id}/test` — Test permissions
- `DELETE /api/v1/social-accounts/{id}` — Disconnect account
- `POST /api/v1/posts/{id}/publish` — Queue per-target publishing
- `GET /api/v1/publishing-jobs` — View publishing queue and attempts
- `POST /api/v1/publishing-jobs/{id}/retry` — Retry failed publication

### Billing & Admin Endpoints (Milestone 7)
- `GET /api/v1/billing/plans` — List plans
- `GET /api/v1/billing/subscription` — Current subscription status
- `POST /api/v1/billing/checkout` — Create checkout session
- `GET /api/v1/usage` — Current period usage against quotas
- `POST /api/v1/webhooks/billing/{provider}` — Process billing webhook
- `GET /api/v1/admin/tenants` — Platform admin tenant list

