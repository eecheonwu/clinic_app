# ADR-005: Email-based Patient Registration Architecture with Email Verification & Audience-Differentiated JWT Auth

**Status**: Accepted  
**Date**: 2026-07-31  
**Deciders**: Antigravity (AI Architect), Clinic Owner, Engineering Lead  

---

## Context / Problem Statement

CMP currently uses phone number + OTP verification for patient registration and login (ADR-004). To expand access and support standard healthcare onboarding workflows, CMP requires email-based patient self-registration with an authentication email containing a password creation link.

Key architectural requirements & constraints:
- **Database Strategy**: Maintain high performance and simplicity without introducing cross-database transaction overhead.
- **Notification Provider**: Integrate email delivery cleanly into the existing Strategy Pattern (`NotificationService` - ADR-004).
- **Password Policy**: Server-side enforcement of strict password complexity rules.
- **Verification Token Security**: Cryptographically safe verification links with short TTL, single-use, and hashed storage.
- **Auth Separation**: Strong separation between patient JWT tokens and staff JWT tokens to prevent token reuse across boundaries.
- **Rate Limiting**: Prevent email flooding (max 3 verification requests per email per 15 minutes).
- **Backward Compatibility**: Keep existing OTP registration operational alongside the new email flow during Phase 1 transition.

---

## Decision

We adopt **Email-based Patient Registration with Audience-Differentiated JWT Authentication and Logical Database Separation**.

### 1. Logical Database Separation Strategy
Instead of physically splitting the database into multiple instances (which introduces distributed transaction complexity), patients and staff remain within the same PostgreSQL 16+ instance (ADR-001). 
- A new table `email_verification_tokens` stores verification tokens.
- Column `is_email_verified` (BOOLEAN NOT NULL DEFAULT FALSE) and `email_verified_at` (TIMESTAMPTZ NULLABLE) are added to the `users` table via Alembic migration.
- Patient and staff accounts share the `users` table but are logically isolated via `role` (`patient` vs staff roles) and distinct JWT audience claims.

### 2. Email Provider & Notification Integration Pattern
Email delivery is added as a new provider adapter (`EmailClient`) within the existing `NotificationService` Strategy Pattern (ADR-004):
- Adapter supports SMTP, SendGrid, and AWS SES configurations.
- Async workers (Celery + Redis) handle email dispatches via `send_auth_email` and `send_email_notification` tasks.
- Transactional templates (`auth_email.html` and `auth_email.txt`) render verification links containing single-use tokens.
- All email dispatches are audited in `notifications_log`.

### 3. Password Complexity Policy
Patient passwords created during verification must meet server-side validation:
- Minimum 8 characters.
- At least 1 uppercase letter (`A-Z`).
- At least 1 lowercase letter (`a-z`).
- At least 1 numeric digit (`0-9`).
- At least 1 special character (`!@#$%^&*()_+-=[]{}|;:,.<>?`).

### 4. Auth Verification Token Strategy
- **Token Generation**: Cryptographically secure 32-byte URL-safe string generated via `secrets.token_urlsafe(32)`.
- **Token Storage**: Plaintext token is never persisted in DB. Stored as a bcrypt hash in `email_verification_tokens` (`token_hash`).
- **TTL**: 60 minutes from generation (`expires_at`).
- **Single-use & Invalidation**: Tokens are marked `is_used = TRUE` immediately upon successful verification. Generating a new verification token automatically invalidates any existing active tokens for that email (`is_expired = TRUE`).

### 5. JWT Token Audience Differentiation
To prevent cross-boundary unauthorized access:
- Patient JWT access tokens include `aud: "patient"`.
- Staff JWT access tokens include `aud: "staff"`.
- FastAPI `RoleChecker` dependency enforces audience verification:
  - Patient endpoints (`/api/v1/appointments/my`, `/api/v1/auth/patient/*`) validate `aud == "patient"`.
  - Staff endpoints (`/api/v1/clinical-records/*`, `/api/v1/admin/*`, `/api/v1/reports/*`) validate `aud == "staff"`.
  - Presenting a patient token at a staff endpoint returns HTTP 403 Forbidden.

### 6. Rate Limiting Strategy
- Email verification registration/resend requests are rate-limited using Redis to **max 3 requests per email per 15 minutes**.
- Exceeding the limit returns HTTP 429 Too Many Requests.

---

## Consequences

### Positive
- **Security**: Cryptographically secure, single-use, hashed verification tokens prevent link hijacking and DB token leakage.
- **Isolation**: Audience-differentiated JWT claims strictly separate patient access from staff operations.
- **Maintainability**: Email notification adapter seamlessly fits into the established `NotificationService` Strategy Pattern (ADR-004).
- **Simplicity**: Single PostgreSQL database avoids cross-database replication or multi-database migration friction.
- **Backward Compatibility**: Phase 1 OTP flows continue to function unaffected during the transition.

### Negative
- Requires maintaining additional template rendering and worker tasks for email.
- Token validation requires querying and bcrypt-comparing active tokens for an email.

### Neutral
- Schema changes added via Alembic nullable/default migrations without downtime.

---

## Rejected Alternatives

1. **Physical Database Separation (Separate DB for Patients)** — Rejected. Adds infrastructure complexity, cross-database foreign key breakage, and sync overhead without operational benefits for a single-tenant clinic system.
2. **Third-Party Identity Provider (Auth0 / Firebase Auth)** — Rejected. Introduces external lock-in, recurring per-user cost, and potential NDPR compliance friction regarding data residence.

---

## Technical Specifications & Schema Changes

### `email_verification_tokens` Table
```sql
CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    is_expired BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_email_verification_tokens_email ON email_verification_tokens(email);
CREATE INDEX ix_email_verification_tokens_expires_at ON email_verification_tokens(expires_at);
```

### Endpoints Defined
- `POST /api/v1/auth/patient/register` — Public (email, phone, profile fields)
- `POST /api/v1/auth/patient/verify-email` — Public (token, password, confirm_password)
- `POST /api/v1/auth/patient/login` — Public (email, password)
- `POST /api/v1/auth/patient/resend-verification` — Public (email)

---

## Implementation Verification Plan

1. Alembic migrations tested for zero-downtime application (`upgrade head` & `downgrade`).
2. Unit tests covering token hash verification, password policy enforcement, and JWT audience claim checks.
3. Integration tests verifying full end-to-end patient registration, email verification, login, and cross-audience HTTP 403 access blocking.
