# Implementation Plan: Email-based Patient Registration with Auth Email & Separate Patient/Staff Login

## Overview

This plan implements email-based patient registration with authentication email delivery and a separate patient/staff login flow. The feature is built alongside the existing phone+OTP system (Phase 1), enabling backward-compatible introduction of the new flow. This is a **Feature Addition / System Evolution** scenario (Scenario 2) governed by `architecture-decision.md` (ARCHITECTURE CHANGE REQUIRED verdict).

**Target Outcome**: Patients can register using email + phone, receive an authentication email with a password creation link, set their password, and log in via a separate patient login endpoint — all while staff login remains unchanged on the existing email+password flow.

**Phased Approach**:

- **Phase 1** (This plan): New email-based registration alongside existing OTP system (backward compatible)
- **Phase 2**: Migrate existing patients to new system
- **Phase 3**: Deprecate OTP-based patient auth

## Architecture Decisions

| Reference | Decision | Impact |
| --- | --- | --- |
| ADR-005 (NEW) | Email-based Patient Registration Architecture | Required before implementation — must cover database separation strategy, email provider integration, password policy, auth token strategy, JWT differentiation |
| architecture-decision.md | Logical separation within same database (recommended) | Avoids cross-database complexity; same PostgreSQL instance, separate auth tables, different JWT claims |
| architecture-decision.md | New ADR-005 required | Triggers sync rules: `new_provider_or_integration` and `architecture_change` |
| ADR-004 (Existing) | Pluggable NotificationService with Strategy Pattern | Email notification delivery integrated as a new provider adapter |
| ADR-001 (Existing) | PostgreSQL 16+ as primary datastore | Schema changes via Alembic migrations; `email_verification_tokens` table added |
| ADR-002 (Existing) | React PWA with Vite | New frontend pages (registration with email, password creation, patient login) |

### Key Technical Decisions

1. **Database Strategy**: Logical separation within the same PostgreSQL database. Patients and staff share the same database instance but use different tables (existing `users` + new `email_verification_tokens`) and different JWT claim audiences.
2. **Email Provider**: Email notification capability added as a new adapter in the existing NotificationService Strategy Pattern (ADR-004). Provider selection (SMTP/SendGrid/AWS SES) to be documented in ADR-005.
3. **Password Policy**: Minimum 8 characters, at least 1 uppercase, 1 lowercase, 1 digit, 1 special character. Server-side validation enforced.
4. **Auth Token Strategy**: Cryptographically random tokens (`secrets.token_urlsafe(32)`); 60-minute TTL; single-use (invalidated after password creation); stored as bcrypt hash in `email_verification_tokens` table.
5. **JWT Token Differentiation**: Patient tokens include `aud: "patient"` claim; staff tokens include `aud: "staff"` claim. This enables separate validation paths and prevents token type confusion.
6. **Rate Limiting**: Email verification requests limited to 3 requests per email per 15 minutes (matching existing OTP rate limit pattern).

## Task List

### 0. Pre-Implementation Tasks (SSOT & ADR)

- [ ] **Task 0.1 — Create ADR-005: Email-based Patient Registration Architecture** (Scope: M)
  - Document database separation strategy: logical separation within same database
  - Document email notification provider selection and integration pattern
  - Document password policy for patients
  - Document auth token strategy for email verification links (60-min TTL, single-use, bcrypt-hashed)
  - Document JWT token differentiation: `aud: "patient"` vs `aud: "staff"` claims
  - Document rate limiting strategy for email verification requests
  - Save to `knowledge/architecture/ADR/ADR-005-email-patient-registration.md`

- [ ] **Task 0.2 — Update SSOT Artifacts (Pre-Implementation)** (Scope: M)
  - Update `knowledge/architecture/C4/system-context.md`: Add email notification provider as a new external system
  - Update `knowledge/architecture/C4/containers.md`: Add email provider container
  - Update `knowledge/architecture/C4/components.md`: Add PatientAuth component, EmailVerification component
  - Update `knowledge/system/services.md`: Add new endpoints and services documentation
  - Update `knowledge/system/data-models.md`: Add `email_verification_tokens` table, `is_email_verified` column, new indexes
  - Update `knowledge/architecture/UML/class-diagrams.md`: Add EmailVerificationToken entity, PatientAuth entity
  - Update `knowledge/architecture/UML/component-diagrams.md`: Add new service components
  - Update `knowledge/architecture/UML/sequence-diagrams.md`: Add email registration flow, email verification flow, password creation flow
  - Update `knowledge/architecture/UML/state-diagrams.md`: Add email verification states, password creation states
  - Update `knowledge/architecture/UML/activity-diagrams.md`: Add email registration control flow
  - Update `knowledge/ssot.yaml`: Update `next_id` to ADR-005; update `completed_tasks`

### 1. Database Tasks

- [ ] **Task 1.1 — Add `email_verification_tokens` Table** (Scope: XS)
  - Create Alembic migration for new table:
    - `id` (UUID PK, `gen_random_uuid()`)
    - `email` (VARCHAR(255), NOT NULL)
    - `token_hash` (VARCHAR(255), NOT NULL) — bcrypt hash of the verification token
    - `attempts` (INTEGER, default 0, max 5)
    - `is_used` (BOOLEAN, default FALSE)
    - `is_expired` (BOOLEAN, default FALSE)
    - `expires_at` (TIMESTAMPTZ, NOT NULL) — 60-minute TTL
    - `created_at` (TIMESTAMPTZ, default NOW())
  - Create indexes: `ix_email_verification_tokens_email` on `email`, `ix_email_verification_tokens_expires_at` on `expires_at`
  - **Verification**: Alembic upgrade cleanly applies; verify table and indexes in PostgreSQL

- [ ] **Task 1.2 — Add `is_email_verified` Column to `users` Table** (Scope: XS)
  - Create Alembic migration:
    - Add `is_email_verified` (BOOLEAN, NOT NULL, default FALSE) to `users` table
    - Add `email_verified_at` (TIMESTAMPTZ, nullable) to `users` table
  - Backward-compatible: nullable-first pattern (column added with default, no constraint changes)
  - **Verification**: Existing users get `is_email_verified = FALSE`; no data loss

- [ ] **Task 1.3 — Add `email` NOT NULL Constraint for New Patients** (Scope: XS)
  - Create Alembic migration:
    - Since `email` is already UNIQUE, add NOT NULL constraint for new patient registrations
    - Use `ALTER TABLE users ALTER COLUMN email SET NOT NULL` (only if all existing rows have email populated)
    - If existing NULL emails exist, create a separate data migration to backfill
  - **Verification**: `INSERT INTO users (email) VALUES (NULL)` fails with constraint violation

### 2. Backend Tasks

- [ ] **Task 2.1 — Email Notification Provider Adapter** (Scope: M)
  - Implement email provider adapter in existing NotificationService Strategy Pattern:
    - Create `EmailClient` class in `src/backend/services/notification/providers/email_provider.py`
    - Implement interface: `send_email(to_email, subject, html_body, text_body)`
    - Support configuration via settings: SMTP host/port/credentials or SendGrid/AWS SES API key
    - Integrate with existing `NotificationLog` for delivery tracking
  - Implement Celery task for email sending:
    - `send_auth_email(verification_id, to_email, token)` — generates auth email with password creation link
    - `send_email_notification(to_email, subject, template_name, context_data)`
  - Add email templates:
    - `auth_email.html` — "Click here to create your password" with verification link
    - `auth_email.txt` — Plaintext fallback with the verification link
  - **Verification**: Unit test sends email via mock provider; `NotificationLog` entry created

- [ ] **Task 2.2 — Patient Registration with Email Endpoint** (Scope: M)
  - Implement `POST /api/v1/auth/patient/register` (access: Public):
    - Request schema: `PatientRegisterWithEmailRequest`:

      ```json
      {
        "email": "patient@example.com",
        "phone_number": "+2348012345678",
        "full_name": "John Doe",
        "date_of_birth": "1990-01-15",
        "gender": "male",
        "emergency_contact": "+2348012345679"
      }
      ```

    - Response 200: `{ "message": "An authentication email has been sent to your email address", "email": "patient@example.com" }`
    - Business logic:
      1. Validate email format + uniqueness (check `users.email` — must not already exist)
      2. Validate phone_number uniqueness (check `users.phone_number`)
      3. Validate password policy (enforced at password creation stage, not registration)
      4. Generate cryptographically random token (`secrets.token_urlsafe(32)`)
      5. Store token hash (bcrypt) in `email_verification_tokens` table with 60-min TTL
      6. Invalidate any prior active email verification tokens for this email (single active session)
      7. Enqueue Celery task to send auth email with verification link
      8. Return informational message
    - Rate limiting: 3 requests per email per 15 minutes (Redis-based, matching existing OTP pattern)
    - Error handling:
      - HTTP 409: Email already registered
      - HTTP 429: Rate limit exceeded
      - HTTP 422: Validation error (invalid email, weak password)
  - **Verification**: `POST /api/v1/auth/patient/register` with valid data returns 200; `email_verification_tokens` row created; Celery task enqueued

- [ ] **Task 2.3 — Email Verification & Password Creation Endpoint** (Scope: M)
  - Implement `POST /api/v1/auth/patient/verify-email` (access: Public):
    - Request schema: `PatientVerifyEmailRequest`:

      ```json
      {
        "token": "abc123...",
        "password": "StrongP@ss1",
        "confirm_password": "StrongP@ss1"
      }
      ```

    - Response 200: `{ "access_token": "jwt...", "refresh_token": "jwt...", "token_type": "bearer", "expires_in": 3600 }`
    - Business logic:
      1. Find token by iterating active (non-expired, non-used) tokens and verify bcrypt hash
      2. Validate token not expired (check `expires_at` > NOW())
      3. Validate token not used (check `is_used = FALSE`)
      4. Validate password strength (server-side): min 8 chars, uppercase, lowercase, digit, special
      5. Validate `password == confirm_password`
      6. Mark token as used (`is_used = TRUE`)
      7. Create `users` row with `role = 'patient'`, `email`, `phone_number`, bcrypt `password_hash`, `is_email_verified = TRUE`
      8. Create `patient_profiles` row with registration data
      9. Issue JWT with `aud: "patient"` claim
      10. Return access + refresh tokens
    - Error handling:
      - HTTP 400: Invalid/expired token, password mismatch, weak password
      - HTTP 409: Token already used
    - **Verification**: Valid token + password creates user and returns JWT; expired token returns 400; used token returns 409

- [ ] **Task 2.4 — Patient Login Endpoint** (Scope: S)
  - Implement `POST /api/v1/auth/patient/login` (access: Public):
    - Request schema: `PatientLoginRequest`:

      ```json
      {
        "email": "patient@example.com",
        "password": "StrongP@ss1"
      }
      ```

    - Response 200: `{ "access_token": "jwt...", "refresh_token": "jwt...", "token_type": "bearer", "expires_in": 3600 }`
    - Business logic:
      1. Look up user by email with `role = 'patient'`
      2. Verify bcrypt password hash
      3. Verify `is_email_verified = TRUE`
      4. Issue JWT with `aud: "patient"` claim
      5. Return access + refresh tokens
    - Error handling:
      - HTTP 401: Invalid credentials
      - HTTP 403: Email not verified
    - **Verification**: Login with valid patient credentials returns JWT; login with wrong password returns 401; unverified email returns 403

- [ ] **Task 2.5 — Resend Verification Email Endpoint** (Scope: XS)
  - Implement `POST /api/v1/auth/patient/resend-verification` (access: Public):
    - Request schema: `ResendVerificationRequest`:

      ```json
      {
        "email": "patient@example.com"
      }
      ```

    - Response 200: `{ "message": "A new authentication email has been sent to your email address" }`
    - Business logic:
      1. Verify email is not already registered (if user exists with `is_email_verified = TRUE`, return 409)
      2. Invalidate prior active verification tokens
      3. Generate new token, hash, store with new 60-min TTL
      4. Enqueue Celery task to resend auth email
    - Rate limiting: 3 requests per email per 15 minutes (shared counter with registration)
    - **Verification**: Resend creates new token, invalidates old one; rate limit enforced

- [ ] **Task 2.6 — JWT Token Differentiation & Auth Middleware** (Scope: S)
  - Update JWT token generation:
    - Patient tokens: include `aud: "patient"` claim
    - Staff tokens: include `aud: "staff"` claim (existing behavior, explicit)
  - Update `POST /api/v1/auth/login` (existing staff login):
    - Restrict to staff roles only (`receptionist`, `doctor`, `manager`, `admin`, `executive`)
    - Return JWT with `aud: "staff"` claim
  - Implement audience-aware `RoleChecker` dependency:
    - Patient endpoints validate `aud: "patient"` AND appropriate role
    - Staff endpoints validate `aud: "staff"` AND appropriate role
    - Prevent patient tokens from accessing staff endpoints and vice versa
  - **Verification**: Patient JWT cannot access staff endpoints; staff JWT cannot access patient login

- [ ] **Task 2.7 — Update Existing Auth Endpoints for Deprecation Path** (Scope: S)
  - Modify `POST /api/v1/auth/register` (existing):
    - Add deprecation warning header: `Deprecation: true` and `Sunset: <date>`
    - Keep functional for backward compatibility
  - Modify `POST /api/v1/auth/verify-request` (existing):
    - Add deprecation warning header
    - Keep functional for backward compatibility
  - Modify `POST /api/v1/auth/verify-code` (existing):
    - Add deprecation warning header
    - Keep functional for backward compatibility
  - **Verification**: Existing endpoints still work with deprecation headers; new endpoints function independently

### 3. Frontend Tasks

- [ ] **Task 3.1 — Registration Page with Email Input** (Scope: M)
  - Update existing registration page (`/register` or create `/patient/register`):
    - Add email input field (required, with email format validation)
    - Keep phone number input (required, Nigerian format)
    - Keep profile fields: full_name, date_of_birth, gender, emergency_contact
    - On submit: call `POST /api/v1/auth/patient/register`
    - On success: display informational message "An authentication email has been sent to your email address"
    - Add email verification status indicator (if email already sent, show resend option)
  - **Verification**: Registration form submits with email; success message displayed; no password field on registration page

- [ ] **Task 3.2 — Password Creation Page** (Scope: M)
  - Create new page `/patient/create-password`:
    - Extract token from URL query parameter (`?token=abc123...`)
    - Display "Create Password" form with:
      - "New Password" input (with strength indicator)
      - "Confirm Password" input
      - Password requirements checklist (min 8 chars, uppercase, lowercase, digit, special)
    - On submit: call `POST /api/v1/auth/patient/verify-email` with token + password + confirm_password
    - On success: redirect to patient dashboard (auto-logged in with returned JWT)
    - On error: display appropriate error message (expired token, weak password, etc.)
    - Handle expired token: show "Link expired" message with "Resend verification email" button
    - Handle used token: show "Link already used" message with redirect to login
  - **Verification**: Navigate to `/patient/create-password?token=valid_token` → create password → auto-login → dashboard

- [ ] **Task 3.3 — Patient Login Page** (Scope: S)
  - Create new patient login page `/patient/login`:
    - Email input field
    - Password input field
    - "Forgot password?" link (placeholder for Phase 2)
    - "Don't have an account? Register" link to `/patient/register`
    - On submit: call `POST /api/v1/auth/patient/login`
    - On success: store JWT, redirect to patient dashboard
    - On error: display "Invalid email or password" message
  - Update existing staff login page `/login`:
    - Keep existing staff login (email + password)
    - Add "Are you a patient?" link to `/patient/login`
    - Keep as staff-only entry point
  - **Verification**: Patient login page accessible at `/patient/login`; staff login at `/login`; tokens don't cross-access

- [ ] **Task 3.4 — Auth State Management & Route Guards** (Scope: S)
  - Update JWT token handling:
    - Decode `aud` claim from JWT
    - Store patient vs staff token type in auth state
    - Implement route guards for patient vs staff routes
    - Patient routes: `/patient/*` (dashboard, appointments, etc.)
    - Staff routes: `/dashboard/*`, `/clinical/*`, `/reports/*`, `/admin/*`
  - Update login/logout flow:
    - Patient login redirects to `/patient/dashboard`
    - Staff login redirects to `/dashboard`
    - Logout clears both token types
  - **Verification**: Patient cannot access staff routes; staff cannot access patient routes; token refresh respects audience

### 4. Testing Tasks

- [ ] **Task 4.1 — Unit Tests: Email Verification Token Service** (Scope: S)
  - Test token generation: cryptographic randomness, bcrypt hashing
  - Test token validation: valid token, expired token (set TTL to 0), used token, tampered token
  - Test password policy: valid passwords, weak passwords (missing uppercase, lowercase, digit, special, too short)
  - Test single-use enforcement: token invalidated after successful verification
  - Test active session invalidation: new registration invalidates prior token
  - Test rate limiting: 3 requests per email per 15 minutes, HTTP 429 on 4th

- [ ] **Task 4.2 — Unit Tests: JWT Audience Differentiation** (Scope: XS)
  - Test patient JWT generation: `aud: "patient"` claim
  - Test staff JWT generation: `aud: "staff"` claim
  - Test audience validation: patient JWT rejected on staff endpoint, staff JWT rejected on patient endpoint
  - Test backward compatibility: existing staff tokens still work on staff endpoints

- [ ] **Task 4.3 — Unit Tests: Email Notification Provider** (Scope: S)
  - Test email sending via mock provider
  - Test email template rendering (HTML + plaintext)
  - Test Celery task enqueueing for auth email
  - Test `NotificationLog` entry creation for email delivery
  - Test provider failover (if email provider fails, log error — no SMS fallback for auth email)

- [ ] **Task 4.4 — Integration Tests: Email Registration Flow** (Scope: M)
  - Full flow: register with email → verify token stored in DB → generate auth email → extract token from email → call verify-email endpoint with password → verify user created in DB → login with email+password → access patient endpoint
  - Expired token flow: register with email → wait for token expiry → call verify-email → verify 400 response
  - Used token flow: register → verify email → create password → try verifying same token → verify 409 response
  - Rate limit flow: register 4 times with same email in 15 minutes → verify 429 on 4th request
  - Resend flow: register → resend → verify old token invalidated, new token stored → verify with new token

- [ ] **Task 4.5 — Integration Tests: Separate Login Flows** (Scope: S)
  - Patient login: register patient → verify email → login with patient email+password → access patient endpoint → verify staff endpoint returns 403
  - Staff login: login with existing staff credentials → access staff endpoint → verify patient endpoint returns 403
  - Cross-token test: patient JWT used on staff endpoint → 403; staff JWT used on patient endpoint → 403
  - Deprecation test: existing OTP endpoints still work → verify deprecation headers present

- [ ] **Task 4.6 — Frontend Tests** (Scope: S)
  - Registration page: render with email field, validate email format, submit calls correct API
  - Password creation page: render with token from URL, validate password strength, submit calls verify-email
  - Patient login page: render, submit calls patient login, success redirects to patient dashboard
  - Staff login page: unchanged, staff login still works, "Are you a patient?" link present
  - Route guards: patient routes redirect to patient login when unauthenticated; staff routes redirect to staff login
  - Token handling: patient JWT stored separately; audience claim checked on route access

- [ ] **Task 4.7 — End-to-End Tests** (Scope: M)
  - Full patient journey (new flow): navigate to `/patient/register` → fill email + phone + profile → submit → see "auth email sent" message → navigate to password creation page with token → create password → auto-login → access patient dashboard
  - Full patient journey (existing flow): existing OTP registration still works
  - Full staff journey: staff login → access dashboard → no impact from patient auth changes
  - Cross-boundary: patient JWT cannot access staff dashboard; staff JWT cannot access patient dashboard

### 5. Deployment Tasks

- [ ] **Task 5.1 — Email Provider Configuration** (Scope: S)
  - Add email provider configuration to environment settings:
    - `EMAIL_PROVIDER`: `smtp` / `sendgrid` / `ses`
    - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (for SMTP)
    - `SENDGRID_API_KEY` (for SendGrid)
    - `AWS_SES_REGION`, `AWS_SES_ACCESS_KEY`, `AWS_SES_SECRET_KEY` (for SES)
    - `EMAIL_FROM_ADDRESS`: `noreply@clinicplatform.com`
    - `EMAIL_FROM_NAME`: `Clinic Platform`
    - `EMAIL_VERIFICATION_BASE_URL`: `https://app.clinicplatform.com/patient/create-password`
  - Store secrets in AWS Secrets Manager
  - Configure DKIM/SPF/DMARC DNS records for email sending domain
  - **Verification**: Email sending works from staging environment; SPF/DKIM passes

- [ ] **Task 5.2 — Alembic Migration Deployment** (Scope: XS)
  - Add new migration scripts to deployment pipeline
  - Ensure backward-compatible: `is_email_verified` column added with default FALSE
  - Test migration on staging: upgrade → verify → downgrade → verify
  - **Verification**: Migration runs without data loss; downgrade is clean

- [ ] **Task 5.3 — Monitoring & Alerting for Email Delivery** (Scope: XS)
  - Add email delivery metrics to `NotificationLog` monitoring
  - Set up CloudWatch alarm for email delivery failure rate > 5%
  - Add email-specific dashboard panel in existing notification delivery dashboard
  - **Verification**: Email delivery attempts tracked in `NotificationLog`; dashboard shows email metrics

## Checkpoints & Verifications

- **Checkpoint 0 — ADR-005 Approved**: ADR-005 document created and approved; SSOT artifacts updated to reflect new architecture. Required before any implementation begins.
- **Checkpoint 1 — Schema Migrations Complete**: `email_verification_tokens` table created; `is_email_verified` column added to `users`; Alembic upgrade/downgrade works cleanly. All existing data preserved.
- **Checkpoint 2 — Email Registration Flow Functional**: `POST /api/v1/auth/patient/register` creates verification token, enqueues email task. `POST /api/v1/auth/patient/verify-email` validates token, enforces password policy, creates user, returns JWT. `POST /api/v1/auth/patient/login` authenticates with email+password. Rate limiting enforced (3/15min).
- **Checkpoint 3 — Login Separation Verified**: Patient login at `/api/v1/auth/patient/login` returns JWT with `aud: "patient"`. Staff login at `/api/v1/auth/login` returns JWT with `aud: "staff"`. Patient JWT cannot access staff endpoints. Staff JWT cannot access patient endpoints. Existing OTP endpoints still functional with deprecation headers.
- **Checkpoint 4 — Frontend Flow Complete**: Patient registration page with email input → password creation page with token → patient login page → patient dashboard. Staff login page unchanged with patient link. Route guards enforce audience separation.
- **Checkpoint 5 — Email Delivery Verified**: Auth email sent with verification link. Link works (creates password). Expired link returns appropriate error. Resend functionality works. Rate limiting enforced. `NotificationLog` tracks all email attempts.
- **Checkpoint 6 — All Tests Pass**: Unit tests (token service, JWT differentiation, email provider) pass. Integration tests (full registration flow, login separation, rate limiting, resend) pass. Frontend tests (registration page, password creation, route guards) pass. E2E tests (full patient journey, full staff journey, cross-boundary) pass.

## Risks and Constraints

| Risk | Impact | Mitigation |
| --- | --- | --- |
| **Email deliverability issues (Nigerian ISPs)** | Auth emails not received → patients cannot complete registration | Multiple email provider options (SMTP/SendGrid/SES); SPF/DKIM/ DMARC configuration; `NotificationLog` monitoring; resend endpoint for recovery |
| **Token interception in email** | Account takeover if verification link intercepted | Short TTL (60 min); single-use token; bcrypt-hashed token storage; HTTPS-only links |
| **Backward compatibility with OTP system** | Existing patients with OTP-only accounts lose access | Phase 1 keeps OTP system fully functional; Phase 2 migration plan; deprecation headers on old endpoints |
| **Password policy friction** | Patients abandon registration due to strict password rules | Clear password requirements displayed on creation page; strength indicator; balance between security and UX |
| **Rate limiting false positives** | Legitimate users blocked from resending verification | 15-minute window with 3-request limit matches existing OTP pattern; clear error message with retry-after header |
| **JWT audience claim enforcement gaps** | Token type confusion — patient token used for staff actions | Centralized `RoleChecker` dependency with audience validation; comprehensive integration tests; audit logging for cross-boundary access attempts |
| **Email provider API throttling** | Bulk email sends delayed | Celery async queue for email delivery; exponential backoff on provider throttling; failover to secondary email provider if configured |
| **SSOT synchronization debt** | Architecture drift if SSOT not updated concurrently | Task 0.2 enforces pre-implementation SSOT update; post-implementation sync required per `ssot.yaml` sync rules |

---

## Appendix: Affected Files & Artifacts

| Category | Artifact | Action |
| --- | --- | --- |
| **ADR** | `knowledge/architecture/ADR/ADR-005-email-patient-registration.md` | CREATE |
| **C4** | `knowledge/architecture/C4/system-context.md` | UPDATE — Add email provider |
| **C4** | `knowledge/architecture/C4/containers.md` | UPDATE — Add email container |
| **C4** | `knowledge/architecture/C4/components.md` | UPDATE — Add PatientAuth, EmailVerification components |
| **System** | `knowledge/system/services.md` | UPDATE — Add new endpoints |
| **System** | `knowledge/system/data-models.md` | UPDATE — Add new table, column |
| **UML** | `knowledge/architecture/UML/class-diagrams.md` | UPDATE — Add new entities |
| **UML** | `knowledge/architecture/UML/component-diagrams.md` | UPDATE — Add new components |
| **UML** | `knowledge/architecture/UML/sequence-diagrams.md` | UPDATE — Add new flows |
| **UML** | `knowledge/architecture/UML/state-diagrams.md` | UPDATE — Add new states |
| **UML** | `knowledge/architecture/UML/activity-diagrams.md` | UPDATE — Add new control flows |
| **SSOT** | `knowledge/ssot.yaml` | UPDATE — ADR-005, completed_tasks |
| **Database** | Alembic migration: `email_verification_tokens` table | CREATE |
| **Database** | Alembic migration: `is_email_verified` column | ALTER |
| **Backend** | `services/notification/providers/email_provider.py` | CREATE |
| **Backend** | `services/auth/patient_auth_service.py` | CREATE |
| **Backend** | `api/routers/auth_patient.py` | CREATE |
| **Backend** | `schemas/auth_patient.py` | CREATE |
| **Backend** | `core/security.py` | MODIFY — JWT audience |
| **Backend** | `api/routers/auth.py` | MODIFY — Deprecation headers |
| **Frontend** | `pages/patient/register.tsx` | CREATE/UPDATE |
| **Frontend** | `pages/patient/create-password.tsx` | CREATE |
| **Frontend** | `pages/patient/login.tsx` | CREATE |
| **Frontend** | `pages/staff/login.tsx` | MODIFY — Add patient link |
| **Frontend** | `services/auth.ts` | MODIFY — JWT audience handling |
| **Frontend** | `components/RouteGuard.tsx` | MODIFY — Audience-aware routing |
| **Tests** | `tests/test_auth_patient.py` | CREATE |
| **Tests** | `tests/test_email_provider.py` | CREATE |
| **Tests** | `tests/test_jwt_audience.py` | CREATE |
| **Tests** | `tests/test_auth_routes.py` | MODIFY — Add deprecation tests |
| **Config** | `.env` / AWS Secrets Manager | ADD — Email provider config |
| **Infra** | DNS records | ADD — SPF/DKIM/DMARC for email domain |
