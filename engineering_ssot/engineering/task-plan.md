# Task Plan: Email-based Patient Registration with Auth Email & Separate Patient/Staff Login

**Scenario**: Feature Addition / System Evolution (Scenario 2)
**Source**: `implementation-plan.md` — Email-based Patient Registration with Auth Email & Separate Patient/Staff Login
**ADRs**: ADR-005 (NEW), ADR-001, ADR-002, ADR-004 (Existing)
**Target Phase**: Phase 1 — New email-based registration alongside existing OTP system (backward compatible)

---

## Dependency Graph

```
Pre-Implementation (SSOT) ──────┐
                                ├── Vertical Slice 1 (Email Infrastructure)
                                │         │
                                ├── Vertical Slice 2 (Patient Registration)
                                │         │
                                ├── Vertical Slice 3 (Email Verification)
                                │         │
                                ├── Vertical Slice 4 (Patient Login & Auth)
                                │         │
                                ├── Vertical Slice 5 (Edge Cases)
                                │         │
                                ├── Vertical Slice 6 (Testing)
                                │         │
                                └── Vertical Slice 7 (Deployment)
```

**Rule**: Each vertical slice groups DB schema, backend, frontend, and tests together for a single feature.

---

## Checkpoint 0: Pre-Implementation (SSOT & ADR)

### Task 0.1: Create ADR-005 — Email-based Patient Registration Architecture

**Description:**
Create a new Architecture Decision Record (ADR-005) documenting the email-based patient registration architecture. This ADR must cover: database separation strategy (logical separation within same database), email notification provider selection and integration pattern (as a new adapter in the existing NotificationService Strategy Pattern), password policy for patients (min 8 chars, uppercase, lowercase, digit, special), auth token strategy for email verification links (60-min TTL, single-use, bcrypt-hashed tokens), JWT token differentiation (`aud: "patient"` vs `aud: "staff"` claims), and rate limiting strategy for email verification requests (3 requests per email per 15 minutes).

**Acceptance criteria:**
- [ ] ADR-005 document created at `knowledge/architecture/ADR/ADR-005-email-patient-registration.md`
- [ ] Covers all required topics: database strategy, email provider, password policy, auth token strategy, JWT differentiation, rate limiting
- [ ] Follows the existing ADR format (same structure as ADR-001 through ADR-004)

**Verification:**
- [ ] File exists at `knowledge/architecture/ADR/ADR-005-email-patient-registration.md`
- [ ] ADR is consistent with existing ADR-004 (NotificationService Strategy Pattern) and ADR-001 (PostgreSQL)

**Dependencies:**
- None

**Files likely touched:**
- `knowledge/architecture/ADR/ADR-005-email-patient-registration.md` (CREATE)

**Estimated scope:**
- Medium

---

### Task 0.2: Update SSOT Artifacts (Pre-Implementation)

**Description:**
Update all SSOT architecture artifacts to reflect the new email-based patient registration architecture before any implementation begins. Email notification provider as external system in C4 context. New PatientAuth and EmailVerification components. Document `email_verification_tokens` table, `is_email_verified` column. Add UML sequences for email registration, verification, password creation flows. Update `ssot.yaml` with ADR-005.

**Acceptance criteria:**
- [ ] C4 system-context, containers, components updated
- [ ] services.md and data-models.md updated
- [ ] UML diagrams (class, component, sequence, state, activity) updated
- [ ] ssot.yaml updated with ADR-005

**Verification:**
- [ ] All SSOT files consistent with each other and ADR-005
- [ ] `knowledge/ssot.yaml` shows ADR-005

**Dependencies:**
- Task 0.1

**Files likely touched:**
- Multiple files under `knowledge/architecture/` and `knowledge/system/`
- `knowledge/ssot.yaml`

**Estimated scope:**
- Medium

---

## Checkpoint 1: Email Infrastructure (Vertical Slice 1)

### Task 1: Email Verification Tokens Schema + Email Notification Provider

**Description:**
(1) Alembic migration for `email_verification_tokens` table: id (UUID PK), email (VARCHAR(255), NOT NULL), token_hash (VARCHAR(255), NOT NULL — bcrypt), attempts (INTEGER, default 0, max 5), is_used (BOOLEAN, default FALSE), is_expired (BOOLEAN, default FALSE), expires_at (TIMESTAMPTZ, NOT NULL — 60-min TTL), created_at (TIMESTAMPTZ). Indexes on email and expires_at. (2) Email notification provider as new adapter in NotificationService Strategy Pattern: `EmailClient` class with `send_email(to_email, subject, html_body, text_body)`. Integrate with `NotificationLog`. Celery tasks: `send_auth_email` and `send_email_notification`. Email templates: `auth_email.html` and `auth_email.txt`.

**Acceptance criteria:**
- [ ] Alembic migration creates `email_verification_tokens` table
- [ ] Indexes on email and expires_at
- [ ] EmailClient implements send_email interface
- [ ] Celery tasks for auth email and email notification
- [ ] Email templates created

**Verification:**
- [ ] `alembic upgrade head` — table exists in PostgreSQL
- [ ] `alembic downgrade -1` — table removed
- [ ] Unit test sends email via mock provider; NotificationLog entry created
- [ ] Celery task `send_auth_email` enqueues successfully

**Dependencies:**
- Task 0.2

**Files likely touched:**
- `alembic/versions/` (NEW migration)
- `src/backend/services/notification/providers/email_provider.py` (CREATE)
- `src/backend/workers/tasks.py` (MODIFY)
- `src/backend/core/config.py` (MODIFY)
- `tests/test_email_provider.py` (CREATE)

**Estimated scope:**
- Medium

---

## Checkpoint 2: Patient Registration with Email (Vertical Slice 2)

### Task 2: Patient Registration with Email — Backend + Frontend + Schema

**Description:**
(1) Alembic migration: add `is_email_verified` (BOOLEAN, NOT NULL, default FALSE) and `email_verified_at` (TIMESTAMPTZ, nullable) to `users` table. (2) `POST /api/v1/auth/patient/register` (public): validate email format/uniqueness, validate phone uniqueness, generate cryptographically random token (`secrets.token_urlsafe(32)`), store bcrypt hash in `email_verification_tokens` with 60-min TTL, invalidate prior tokens, enqueue Celery auth email. Rate limit 3/15min. Errors: 409 (email exists), 429 (rate limit), 422 (validation). (3) Frontend `/patient/register` page with email, phone, profile fields. No password field.

**Acceptance criteria:**
- [ ] Alembic migration adds is_email_verified, email_verified_at columns
- [ ] Backward compatible (existing users get FALSE)
- [ ] Registration endpoint returns 200 with success message
- [ ] Token stored in email_verification_tokens as bcrypt hash
- [ ] Celery task enqueued for auth email
- [ ] Rate limit 3/15min, HTTP 429 on 4th
- [ ] HTTP 409 if email already registered
- [ ] Frontend registration page at `/patient/register` renders correctly

**Verification:**
- [ ] `curl -X POST /api/v1/auth/patient/register` with valid data returns 200
- [ ] Check `email_verification_tokens` table has new row
- [ ] Duplicate email returns 409
- [ ] 4th request within 15min returns 429
- [ ] Navigate to `/patient/register` — form renders with email field

**Dependencies:**
- Task 1

**Files likely touched:**
- `alembic/versions/` (NEW migration)
- `src/backend/api/v1/auth/` (NEW router for patient auth)
- `src/backend/api/v1/auth/schemas.py` (MODIFY)
- `src/backend/services/auth_service.py` (MODIFY)
- `src/backend/workers/tasks.py` (MODIFY)
- `src/frontend/src/pages/Patient/PatientRegisterPage.tsx` (CREATE)
- `tests/test_auth_patient.py` (CREATE)

**Estimated scope:**
- Medium

---

## Checkpoint 3: Email Verification & Password Creation (Vertical Slice 3)

### Task 3: Email Verification & Password Creation — Backend + Frontend

**Description:**
(1) `POST /api/v1/auth/patient/verify-email` (public): receive token + password + confirm_password. Find token by iterating active tokens and verifying bcrypt hash. Validate token not expired, not used. Validate password strength (min 8, uppercase, lowercase, digit, special). Validate password == confirm_password. Mark token as used. Create `users` row (role=patient, email, phone_number, bcrypt password_hash, is_email_verified=TRUE). Create `patient_profiles` row. Issue JWT with `aud: "patient"`. Errors: 400 (invalid/expired token, password mismatch, weak password), 409 (token already used). (2) Frontend `/patient/create-password` page: extract token from URL `?token=...`, password form with strength indicator and requirements checklist, submit calls verify-email, auto-redirect to patient dashboard on success. Handle expired/used token errors.

**Acceptance criteria:**
- [ ] Verify-email endpoint creates user and returns JWT for valid token
- [ ] Password validation enforced server-side
- [ ] Expired token returns 400
- [ ] Used token returns 409
- [ ] Password mismatch returns 400
- [ ] JWT has `aud: "patient"` claim
- [ ] Password creation page renders with token from URL
- [ ] Password strength indicator works
- [ ] Expired token page shows "Link expired" with resend button
- [ ] Used token page shows "Link already used" with login redirect

**Verification:**
- [ ] `curl -X POST /api/v1/auth/patient/verify-email` with valid token returns 200 + JWT
- [ ] Expired token returns 400
- [ ] Used token returns 409
- [ ] Weak password returns 400
- [ ] Navigate to `/patient/create-password?token=valid_token` — form renders
- [ ] Create password — auto-redirect to patient dashboard

**Dependencies:**
- Task 2

**Files likely touched:**
- `src/backend/api/v1/auth/` (MODIFY)
- `src/backend/api/v1/auth/schemas.py` (MODIFY)
- `src/backend/services/auth_service.py` (MODIFY)
- `src/backend/core/security.py` (MODIFY)
- `src/frontend/src/pages/Patient/PatientCreatePasswordPage.tsx` (CREATE)
- `tests/test_auth_patient.py` (MODIFY)

**Estimated scope:**
- Medium

---

## Checkpoint 4: Patient Login & Auth Separation (Vertical Slice 4)

### Task 4: JWT Audience Differentiation + Patient Login + Frontend Login + Route Guards

**Description:**
(1) Update JWT: patient tokens get `aud: "patient"`, staff tokens get `aud: "staff"`. Restrict `POST /api/v1/auth/login` to staff roles only. Audience-aware RoleChecker — patient endpoints validate aud:patient, staff endpoints validate aud:staff. (2) `POST /api/v1/auth/patient/login`: accept email + password, look up user by email with role=patient, verify bcrypt password, verify is_email_verified=TRUE, issue JWT with aud:patient. Errors: 401 (invalid), 403 (unverified). (3) Frontend patient login at `/patient/login`, staff login `/login` with "Are you a patient?" link. (4) Update AuthContext with audience-aware token handling, route guards for `/patient/*` vs staff routes.

**Acceptance criteria:**
- [ ] Patient JWT includes `aud: "patient"`
- [ ] Staff JWT includes `aud: "staff"`
- [ ] Staff login endpoint restricted to staff roles
- [ ] Patient login works with email + password
- [ ] Patient JWT cannot access staff endpoints (403)
- [ ] Staff JWT cannot access patient endpoints (403)
- [ ] Unverified email login returns 403
- [ ] Patient login page at `/patient/login` renders
- [ ] Staff login page has patient link
- [ ] Route guards enforce audience separation

**Verification:**
- [ ] Patient login returns JWT with aud:patient
- [ ] Staff login returns JWT with aud:staff
- [ ] Patient JWT on staff endpoint → 403
- [ ] Staff JWT on patient endpoint → 403
- [ ] Patient login → redirect to `/patient/dashboard`
- [ ] Staff login → redirect to `/dashboard`

**Dependencies:**
- Task 3

**Files likely touched:**
- `src/backend/core/security.py` (MODIFY)
- `src/backend/services/auth_service.py` (MODIFY)
- `src/backend/api/v1/auth/router.py` (MODIFY)
- `src/backend/api/v1/auth/schemas.py` (MODIFY)
- `src/frontend/src/pages/Patient/PatientLoginPage.tsx` (CREATE)
- `src/frontend/src/pages/auth/LoginPage.tsx` (MODIFY)
- `src/frontend/src/contexts/AuthContext.tsx` (MODIFY)
- `src/frontend/src/services/api.ts` (MODIFY)
- `src/frontend/src/components/RouteGuard.tsx` (CREATE)
- `tests/test_jwt_audience.py` (CREATE)

**Estimated scope:**
- Large

---

## Checkpoint 5: Edge Cases & Deprecation (Vertical Slice 5)

### Task 5: Resend Verification + Deprecation Headers + NOT NULL Constraint

**Description:**
(1) `POST /api/v1/auth/patient/resend-verification`: accept email, verify not already verified (409 if is_email_verified=TRUE), invalidate prior tokens, generate new token, enqueue Celery task. Rate limit 3/15min shared with registration. (2) Add `Deprecation: true` and `Sunset` headers to existing OTP endpoints (`/register`, `/verify-request`, `/verify-code`). Keep functional. (3) Alembic migration: `ALTER TABLE users ALTER COLUMN email SET NOT NULL`. Backfill if NULL emails exist.

**Acceptance criteria:**
- [ ] Resend creates new token, invalidates old one
- [ ] Rate limit enforced (3/15min)
- [ ] HTTP 409 if already verified
- [ ] Existing OTP endpoints functional with deprecation headers
- [ ] email column NOT NULL constraint applied

**Verification:**
- [ ] Resend returns 200, old token invalidated
- [ ] Existing OTP endpoints return Deprecation header
- [ ] INSERT with NULL email fails

**Dependencies:**
- Tasks 2, 3

**Files likely touched:**
- `alembic/versions/` (NEW migration)
- `src/backend/api/v1/auth/` (MODIFY)
- `src/backend/api/v1/auth/router.py` (MODIFY)
- `tests/test_auth_patient.py` (MODIFY)

**Estimated scope:**
- Medium

---

## Checkpoint 6: Testing (Vertical Slice 6)

### Task 6: Unit Tests — Token Service, JWT Audience, Email Provider

**Description:**
(1) Token service tests: cryptographic randomness, bcrypt hashing, valid/expired/used/tampered token validation, password policy (min 8, uppercase, lowercase, digit, special), single-use enforcement, rate limiting (3/15min, 429 on 4th). (2) JWT audience tests: patient token aud:patient, staff token aud:staff, audience validation (patient token rejected on staff endpoint), backward compatibility. (3) Email provider tests: mock provider sending, template rendering (HTML + plaintext), Celery task enqueueing, NotificationLog entry, provider failover.

**Acceptance criteria:**
- [ ] All unit tests pass
- [ ] Coverage for token generation, validation, password policy, rate limiting
- [ ] Coverage for JWT audience claims and validation
- [ ] Coverage for email sending, templates, Celery, NotificationLog

**Verification:**
- [ ] `pytest tests/test_auth_patient.py -v` — all pass
- [ ] `pytest tests/test_jwt_audience.py -v` — all pass
- [ ] `pytest tests/test_email_provider.py -v` — all pass

**Dependencies:**
- Tasks 1-5

**Files likely touched:**
- `tests/test_auth_patient.py` (CREATE)
- `tests/test_jwt_audience.py` (CREATE)
- `tests/test_email_provider.py` (CREATE)

**Estimated scope:**
- Medium

---

### Task 7: Integration Tests — Registration Flow & Login Separation

**Description:**
(1) Full flow: register → verify token in DB → call verify-email → user created → login → access patient endpoint. (2) Expired token → 400. (3) Used token → 409. (4) Rate limit → 429 on 4th. (5) Resend → old token invalidated, new token works. (6) Patient login → access patient endpoint → staff endpoint returns 403. (7) Staff login → access staff endpoint → patient endpoint returns 403. (8) Cross-token: patient JWT on staff → 403, staff JWT on patient → 403. (9) Deprecation: OTP endpoints still work with headers.

**Acceptance criteria:**
- [ ] All integration tests pass
- [ ] Full registration flow works end-to-end
- [ ] Error cases handled (expired, used, rate limited)
- [ ] Login separation verified
- [ ] Cross-token blocked
- [ ] OTP endpoints functional with deprecation headers

**Verification:**
- [ ] `pytest tests/integration/test_email_registration_flow.py -v` — all pass
- [ ] `pytest tests/integration/test_login_separation.py -v` — all pass

**Dependencies:**
- Task 6

**Files likely touched:**
- `tests/integration/test_email_registration_flow.py` (CREATE)
- `tests/integration/test_login_separation.py` (CREATE)
- `tests/test_auth_routes.py` (MODIFY)

**Estimated scope:**
- Medium

---

### Task 8: Frontend Tests

**Description:**
(1) Registration page: render, email validation, API call. (2) Password creation page: render with token, password strength, API call. (3) Patient login page: render, submit, success redirect. (4) Staff login page: unchanged, patient link present. (5) Route guards: audience-aware redirects. (6) Token handling: audience claim checked.

**Acceptance criteria:**
- [ ] All frontend tests pass

**Verification:**
- [ ] `npx vitest run` — all pass

**Dependencies:**
- Tasks 2-4

**Files likely touched:**
- `src/frontend/tests/PatientRegisterPage.test.tsx` (CREATE)
- `src/frontend/tests/PatientCreatePasswordPage.test.tsx` (CREATE)
- `src/frontend/tests/PatientLoginPage.test.tsx` (CREATE)
- `src/frontend/tests/StaffLoginPage.test.tsx` (MODIFY)
- `src/frontend/tests/RouteGuard.test.tsx` (CREATE)

**Estimated scope:**
- Medium

---

### Task 9: End-to-End Tests

**Description:**
(1) Full patient journey (new flow): `/patient/register` → fill email + phone + profile → submit → see success message → navigate to password creation page with token → create password → auto-login → patient dashboard. (2) Full patient journey (existing OTP): OTP registration still works. (3) Full staff journey: staff login → dashboard. (4) Cross-boundary: patient JWT cannot access staff dashboard.

**Acceptance criteria:**
- [ ] All E2E tests pass

**Verification:**
- [ ] `npx playwright test tests/e2e/patient-journey.spec.ts` — passes
- [ ] `npx playwright test tests/e2e/staff-journey.spec.ts` — passes
- [ ] `npx playwright test tests/e2e/cross-boundary.spec.ts` — passes

**Dependencies:**
- Tasks 2-5, 7

**Files likely touched:**
- `tests/e2e/patient-journey.spec.ts` (MODIFY)
- `tests/e2e/staff-journey.spec.ts` (MODIFY)
- `tests/e2e/cross-boundary.spec.ts` (CREATE)

**Estimated scope:**
- Medium

---

## Checkpoint 7: Deployment (Vertical Slice 7)

### Task 10: Email Provider Configuration & Alembic Migration Deployment

**Description:**
(1) Email provider settings: EMAIL_PROVIDER, SMTP_HOST/PORT/USER/PASSWORD, SENDGRID_API_KEY, AWS_SES config, EMAIL_FROM_ADDRESS, EMAIL_FROM_NAME, EMAIL_VERIFICATION_BASE_URL. (2) AWS Secrets Manager documentation. (3) DKIM/SPF/DMARC DNS records for email domain. (4) Migration scripts in deployment pipeline. Test staging: upgrade → verify → downgrade → verify.

**Acceptance criteria:**
- [ ] Email configuration added to `.env.example` and settings
- [ ] AWS Secrets Manager documented
- [ ] DKIM/SPF/DMARC documented
- [ ] Migrations tested on staging

**Verification:**
- [ ] Email sending works from staging
- [ ] SPF/DKIM passes
- [ ] Migration runs without data loss; downgrade clean

**Dependencies:**
- Tasks 1-5, 7

**Files likely touched:**
- `src/backend/.env.example` (MODIFY)
- `src/backend/core/config.py` (MODIFY)

**Estimated scope:**
- Small

---

### Task 11: Monitoring & Alerting for Email Delivery

**Description:**
(1) Email delivery metrics in NotificationLog monitoring. (2) CloudWatch alarm for delivery failure > 5%. (3) Email dashboard panel. (4) Verify NotificationLog tracks email attempts.

**Acceptance criteria:**
- [ ] Email metrics in NotificationLog monitoring
- [ ] CloudWatch alarm configured
- [ ] Email dashboard panel created

**Verification:**
- [ ] Email attempts visible in NotificationLog
- [ ] Dashboard shows email metrics

**Dependencies:**
- Task 10

**Files likely touched:**
- `knowledge/deployment/monitoring.md` (UPDATE)
- `infra/cloudwatch/alarms.tf` (MODIFY)

**Estimated scope:**
- XS

---

## Checkpoints Summary

| Checkpoint | Description | Tasks | Verification |
|---|---|---|---|
| Checkpoint 0 | ADR-005 & SSOT Updated | 0.1, 0.2 | ADR-005 created; all SSOT artifacts consistent |
| Checkpoint 1 | Email Infrastructure | 1 | `email_verification_tokens` table created; email provider works |
| Checkpoint 2 | Patient Registration with Email | 2 | Registration endpoint + frontend page functional |
| Checkpoint 3 | Email Verification & Password Creation | 3 | Verify-email endpoint + password creation page functional |
| Checkpoint 4 | Patient Login & Auth Separation | 4 | Patient login, JWT audience, route guards working |
| Checkpoint 5 | Edge Cases & Deprecation | 5 | Resend, deprecation headers, NOT NULL constraint |
| Checkpoint 6 | All Tests Pass | 6, 7, 8, 9 | Unit, integration, frontend, E2E tests all pass |
| Checkpoint 7 | Deployment Ready | 10, 11 | Email configured, monitoring in place |

---

## Affected Files Summary

| Category | Action | Files |
|---|---|---|
| ADR | CREATE | `knowledge/architecture/ADR/ADR-005-email-patient-registration.md` |
| SSOT | UPDATE | C4 diagrams, services.md, data-models.md, UML diagrams, ssot.yaml |
| DB Migrations | CREATE | 2-3 new Alembic migration files |
| Backend | CREATE | `services/notification/providers/email_provider.py`, `api/v1/auth/patient/` router |
| Backend | MODIFY | `core/security.py`, `core/config.py`, `services/auth_service.py`, `workers/tasks.py`, `api/v1/auth/router.py`, `api/v1/auth/schemas.py` |
| Frontend | CREATE | `pages/Patient/PatientRegisterPage.tsx`, `PatientCreatePasswordPage.tsx`, `PatientLoginPage.tsx`, `components/RouteGuard.tsx` |
| Frontend | MODIFY | `pages/auth/LoginPage.tsx`, `contexts/AuthContext.tsx`, `services/api.ts` |
| Tests | CREATE | `tests/test_auth_patient.py`, `tests/test_jwt_audience.py`, `tests/test_email_provider.py`, integration tests, frontend tests, E2E tests |
| Tests | MODIFY | `tests/test_auth_routes.py`, existing frontend tests, E2E tests |
| Config | MODIFY | `.env.example`, `core/config.py` |
| Infra | MODIFY | monitoring, CloudWatch alarms |

---

## References

- `implementation-plan.md` — Email-based Patient Registration with Auth Email & Separate Patient/Staff Login
- `knowledge/architecture/ADR/ADR-004-pluggable-notification-failover.md`
- `knowledge/architecture/ADR/ADR-001-postgresql-primary-datastore.md`
- `knowledge/architecture/ADR/ADR-002-react-pwa-client.md`
- `knowledge/system/services.md`
- `knowledge/system/data-models.md`
- `knowledge/ssot.yaml`
