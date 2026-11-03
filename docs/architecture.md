# Architecture Overview

## System layers

```
┌─────────────────────────────────────────────────────┐
│                  Presentation Layer                  │
│  Desktop web · Mobile web · Android (React Native)  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                Flask Application                     │
│  Auth · Tenant context · Authorization               │
│  REST API (/api/v1) · Jinja views · Validation       │
└──────┬──────────────────────────────────┬────────────┘
       │                                  │
┌──────▼──────┐                ┌──────────▼──────────┐
│ PostgreSQL  │                │   Redis + Celery     │
│             │                │                      │
│ Tenants     │                │ Research tasks       │
│ Users       │                │ AI generation        │
│ Posts       │                │ Publishing           │
│ Usage       │                │ Retries              │
│ Audit logs  │                └──────────────────────┘
└─────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│                External Services                     │
│  LLM (OpenAI/Anthropic) · Image generation           │
│  Meta Graph API · S3-compatible storage              │
└─────────────────────────────────────────────────────┘
```

## Multi-tenancy

Shared PostgreSQL database with `tenant_id` on every tenant-owned record.

Tenant context is always derived from the authenticated user's active `TenantMembership`, never from client-supplied input.

### Tenant isolation rules

1. Every service function that accesses tenant data receives `tenant_id` from the **authenticated session**, not the request body.
2. Permission checks always call `permission_service.has_permission(user_id, tenant_id, permission)`.
3. Never expose one tenant's data based on UUID guessing alone.
4. A user with Owner role in Tenant A has zero permissions in Tenant B unless they also have a membership there.

## Data model relationships

```
users ──────────── tenant_memberships ──── tenants
                   (role, status)              │
                                               ├── subscriptions ── plans
                                               ├── social_accounts
                                               ├── sources
                                               │     └── research_runs
                                               │           └── research_citations
                                               └── posts
                                                     ├── post_versions
                                                     ├── post_media ── media_assets
                                                     ├── post_targets
                                                     │     └── publishing_jobs
                                                     │           └── publishing_attempts
                                                     └── approvals
```

## Content workflow

```
Source submitted → Background research → AI caption generation
      → Image generation → Draft ready for review
      → User edits → User approves (creates PostVersion + Approval)
      → User publishes → Per-target publishing jobs
      → Success/failure tracked per destination
```

## Role permission matrix

| Permission | Owner | Admin | Editor | Publisher |
|-----------|-------|-------|--------|-----------|
| workspace.update | ✅ | ✅ | ❌ | ❌ |
| members.invite | ✅ | ✅ | ❌ | ❌ |
| content.create | ✅ | ✅ | ✅ | ❌ |
| content.generate | ✅ | ✅ | ✅ | ❌ |
| content.approve | ✅ | ✅ | ❌ | ✅ |
| content.publish | ✅ | ✅ | ❌ | ✅ |
| billing.manage | ✅ | ❌ | ❌ | ❌ |
| social_accounts.connect | ✅ | ✅ | ❌ | ❌ |

## Content status transitions

```
DRAFT → GENERATING → READY_FOR_REVIEW → APPROVED → PUBLISHING → PUBLISHED
                                                              ↘ PARTIALLY_PUBLISHED
                                                              ↘ FAILED
```

Any edit after approval invalidates the approval (returns to READY_FOR_REVIEW).

## Security design

- **Passwords**: Argon2id via argon2-cffi
- **Sessions**: Flask-Login with HTTP-only, SameSite cookies + CSRF protection (Flask-WTF)
- **API tokens**: Short-lived JWT or signed tokens for mobile client (Milestone 6)
- **OAuth credentials**: Encrypted at rest using Fernet envelope encryption
- **SSRF protection**: URL validation before fetching any user-submitted URL (Milestone 2)
- **Rate limiting**: Flask-Limiter on all auth and generation endpoints
- **Audit logging**: Immutable audit_logs table for security-sensitive events

## Background processing

All expensive operations run as Celery tasks:
- Source extraction and research
- AI text generation
- Image generation
- Social platform publishing
- Analytics refresh
- Failed job retries

Mobile and web clients receive a `job_id` immediately (HTTP 202) and poll for progress.

