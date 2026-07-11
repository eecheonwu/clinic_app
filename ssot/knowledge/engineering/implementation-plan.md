# Implementation Plan: Clinic Modernization Platform (CMP) — Phase 1 MVP

## Executive Summary

Build and deploy the Clinic Modernization Platform (CMP) — a secure, cloud-hosted digital operations platform for a chain of 3 (scaling to 15) private healthcare clinics. The system transitions clinics from manual paper/WhatsApp workflows to a decoupled React PWA + FastAPI backend with PostgreSQL, providing appointment scheduling with pessimistic locking, clinical record encryption, and a pluggable notification failover chain (WhatsApp → Termii → Infobip). Phase 1 targets a 4-month delivery timeline covering patient self-service, front-desk operations, doctor clinical workflows, and management dashboards.

**Business Goals**:
- BG-001: Reduce receptionist manual scheduling time by 70% within 6 months
- BG-002: Reduce patient appointment no-show rates by 25–30% within 6 months
- BG-003: Digitise 100% of new patient registration & consultation records
- BG-004: Eliminate schedule conflicts and double-bookings for all doctors
- BG-005: Provide real-time consolidated operational dashboards

**Non-Negotiable Constraints**:
- NFR-001: Patient/doctor search queries < 2.0s at 100 concurrent users
- NFR-002: Key page loads < 3.0s on Nigerian 3G/4G
- NFR-003: ≥99.9% uptime Mon–Sat 07:00–20:00 WAT
- NFR-004: Browser caches current-day appointments for ≥2h read-only offline access
- NFR-005: Full NDPR compliance for all patient data storage/processing
- NFR-006: Clinical notes/histories/diagnoses encrypted at rest (AES-256) & in transit (TLS 1.3)
- NFR-007: Immutable audit log for every read/write/modification of patient records
- NFR-008: System admins CANNOT read patient clinical records or consultation notes

---

## Architecture Decisions

| ADR | Decision | Impact |
|---|---|---|
| ADR-001 | PostgreSQL 16+ (AWS RDS) as primary datastore | All scheduling uses `SELECT ... FOR UPDATE` pessimistic locks; Schema via Alembic migrations; pgvector for Phase 2 AI search |
| ADR-002 | Vite + React SPA packaged as PWA with Workbox + Dexie.js | Static S3/CloudFront hosting; Service Worker for ≥2h offline read-only cache; CORS configured for CloudFront domain |
| ADR-003 | Application-level AES-256-GCM column encryption via AWS KMS envelope encryption | Clinical notes encrypted before DB write; KMS key policies scoped to backend IAM role only; DB admins see only ciphertext (NFR-008) |
| ADR-004 | Pluggable NotificationService using Strategy Pattern with async failover (Celery + Redis) | WhatsApp → Termii SMS → Infobip SMS failover chain; `NotificationLog` for delivery tracking; idempotency to prevent duplicates |

### Technology Stack (from Technology Evaluation)

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Vite + React PWA | Static SPA; native Service Worker control for NFR-004; sub-3s load on 3G/4G |
| Backend | FastAPI (Python 3.12+) | Minimal boilerplate; native async/await; Python ecosystem for Phase 2 LLM/AI |
| Database | PostgreSQL 16+ (AWS RDS) | Native `SELECT ... FOR UPDATE`; ACID transactions; pgvector for Phase 2 |
| Offline Cache | Workbox + Dexie.js | Service Worker precache + IndexedDB for ≥2h read-only appointment cache |
| Encryption | AES-256-GCM + AWS KMS | Envelope encryption with DEK caching; NDPR/NFR-008 compliance |
| Notifications | WhatsApp + Termii + Infobip | Strategy Pattern failover; async Celery workers; NotificationLog idempotency |
| Queue | Redis + Celery | Async background task processing for notifications and OTP delivery |
| Hosting | AWS S3 + CloudFront + API Gateway + ECS Fargate | Cost-effective static hosting; managed infrastructure |

### Container Architecture (C4 Level 2)

```
[Patient Browser / Staff Workstation]
        ↓ HTTPS / TLS 1.3
[CloudFront CDN] ──→ [React PWA (browser)]
        ↓ HTTPS API requests
[AWS API Gateway]
        ↓
[FastAPI Application Server]
    ├──→ [PostgreSQL] (reads/writes/pessimistic locks)
    ├──→ [AWS KMS] (encrypt/decrypt clinical records)
    └──→ [Redis Queue]
                ↓
        [Celery Workers]
            ├──→ [WhatsApp API] (primary)
            ├──→ [Termii API] (SMS failover)
            └──→ [Infobip API] (SMS backup)
```

### Key Technical Decisions

- **RBAC Model**: JWT tokens with role claims (`patient`, `receptionist`, `doctor`, `manager`, `admin`, `executive`); FastAPI Security Scopes enforcement; system admins CANNOT read clinical records (NFR-008)
- **Booking Concurrency**: Pessimistic row-level locks (`SELECT ... FOR UPDATE`) on `doctor_availability` and `appointments` tables within serializable transactions; 3.0s transaction timeout; HTTP 409 on conflict (FR-019)
- **OTP Delivery**: WhatsApp-first with 15-second timeout → SMS fallback (Termii → Infobip); 10-min TTL, max 5 attempts, rate-limited to 3 requests/15min per phone; single-use; new request invalidates prior active session
- **Clinical Record Encryption**: Envelope encryption (DEK encrypted by KMS master key); random IV per write (probabilistic encryption); encrypted columns: `encrypted_notes`, `encrypted_diagnosis`, `encrypted_prescriptions`; DEK cached in application memory to reduce KMS API latency
- **Immutable Audit Trail**: `security_audit_logs` written within same DB transaction as clinical record changes (NFR-007); `user_id` stored as UUID without FK to preserve immutability
- **Payment Schema**: Payment states (`pending/deposit_paid/fully_paid/waived/refunded`) included in schema upfront for Phase 2 Paystack/Flutterwave integration (INT-005); no Phase 1 transaction routing
- **Observability**: Structured JSON logs with `correlation_id`; DB query duration monitoring with alarm if >2.0s (NFR-001); `NotificationLog` delivery metrics
- **Patient Penalty System**: Tiered progression (Tier 1 Warning → Tier 2 Soft Flag → Tier 3 Restricted) based on rolling 90-day late cancellation/no-show counts (FR-012–FR-014); staff override for Tier 3 (FR-015); emergency exemption (FR-016); clinic-initiated cancellation exempt (FR-017)
- **Offline Mode**: Read-only IndexedDB cache of current-day appointments; "Offline Mode — Read Only" banner on network loss; writes blocked; IndexedDB purged on logout/session expiry

---

## Task List

### 1. Database Tasks (PostgreSQL 16+ / AWS RDS)

- [x] **Task 1.1 — Initial Alembic Setup & Base Model** (Scope: XS)
  - Configure Alembic with async SQLAlchemy support
  - Set up base declarative model with common timestamp columns (`created_at`, `updated_at`)
  - Configure `env.py` for PostgreSQL 16+ target with RDS connection string
  - Set up migration versioning and downgrade scripts

- [x] **Task 1.2 — Core Schema: Users & Authentication** (Scope: S)
  - Create `user_role` enum: `patient`, `receptionist`, `doctor`, `manager`, `admin`, `executive`
  - Create `users` table: `id` (UUID PK, `gen_random_uuid()`), `phone_number` (VARCHAR(15) UNIQUE), `email` (VARCHAR(255) UNIQUE), `password_hash` (VARCHAR(255), bcrypt), `role` (user_role ENUM), `created_at`/`updated_at` (TIMESTAMPTZ)
  - Create `patient_profiles` table: `id` (UUID PK), `user_id` (UUID FK → users, CASCADE DELETE), `full_name` (VARCHAR(255)), `date_of_birth` (DATE), `gender` (VARCHAR(10)), `emergency_contact` (VARCHAR(255)), `created_at` (TIMESTAMPTZ)
  - Create `verification_otps` table: `id` (UUID PK), `phone_number` (VARCHAR(15)), `hashed_otp` (VARCHAR(255)), `attempts` (INTEGER, default 0, max 5), `is_used` (BOOLEAN, default FALSE), `expires_at` (TIMESTAMPTZ, 10-min TTL), `delivery_channel` (VARCHAR(20)), `created_at` (TIMESTAMPTZ)
  - Create indexes: `users.phone_number` (UK), `users.email` (UK)

- [x] **Task 1.3 — Scheduling Schema** (Scope: M)
  - Create `appointment_status` enum: `booked`, `cancelled`, `completed`, `no-show`
  - Create `payment_status` enum: `pending`, `deposit_paid`, `fully_paid`, `waived`, `refunded` (INT-005 placeholder)
  - Create `doctor_availability` table: `id` (UUID PK), `doctor_id` (UUID FK → users, CASCADE DELETE), `branch_id` (VARCHAR(50)), `start_datetime` (TIMESTAMPTZ, CHECK start < end), `end_datetime` (TIMESTAMPTZ), `is_cancelled` (BOOLEAN, default FALSE), `created_at` (TIMESTAMPTZ)
  - Create `appointments` table: `id` (UUID PK), `doctor_id` (UUID FK → users, RESTRICT DELETE), `patient_id` (UUID FK → users, RESTRICT DELETE), `branch_id` (VARCHAR(50)), `start_datetime` (TIMESTAMPTZ, CHECK start < end), `end_datetime` (TIMESTAMPTZ), `status` (appointment_status, default `booked`), `payment_state` (payment_status, default `pending`), `booking_source` (VARCHAR(50): `patient`/`receptionist`/`admin_override`), `created_at`/`updated_at` (TIMESTAMPTZ)
  - Create indexes: `doctor_availability.doctor_id + start_datetime`, `appointments.doctor_id + start_datetime + status`, `appointments.patient_id`
  - **Status**: COMPLETE (2026-07-08) - Appointment and DoctorAvailability models implemented with enums and constraints

- [ ] **Task 1.4 — Clinical Records Schema** (Scope: S)
  - Create `clinical_records` table: `id` (UUID PK), `appointment_id` (UUID UNIQUE FK → appointments, RESTRICT DELETE), `patient_id` (UUID FK → users, RESTRICT DELETE), `doctor_id` (UUID FK → users, RESTRICT DELETE), `encrypted_notes` (TEXT, AES-256-GCM ciphertext), `encrypted_diagnosis` (TEXT, AES-256-GCM ciphertext), `encrypted_prescriptions` (TEXT, AES-256-GCM ciphertext), `kms_key_version` (VARCHAR(100)), `created_at` (TIMESTAMPTZ)
  - Create `security_audit_logs` table: `id` (UUID PK), `user_id` (UUID, NO FK for immutability), `action_type` (VARCHAR(100): `READ_CLINICAL_RECORD`, `WRITE_CLINICAL_RECORD`, `OVERRIDE_BOOKING`, etc.), `patient_id` (UUID), `ip_address` (VARCHAR(45)), `timestamp` (TIMESTAMPTZ, default CURRENT_TIMESTAMP), `action_details` (TEXT)
  - CRITICAL: All clinical columns store ciphertext only; decryption only in application memory for authenticated `doctor` role users (NFR-006, NFR-008)
  - Create indexes: `clinical_records.patient_id`, `clinical_records.doctor_id`, `security_audit_logs.user_id + timestamp`

- [ ] **Task 1.5 — Notification & Supporting Schema** (Scope: XS)
  - Create `notifications_log` table: `id` (UUID PK), `recipient` (VARCHAR(255)), `delivery_type` (VARCHAR(20): `whatsapp`/`sms`), `provider` (VARCHAR(50): `whatsapp`/`termii`/`infobip`), `template_name` (VARCHAR(100)), `status` (VARCHAR(50)), `error_code` (VARCHAR(100)), `sent_at` (TIMESTAMPTZ), `delivery_attempts` (INTEGER)
  - Create indexes: `notifications_log.recipient + sent_at`, `notifications_log.provider + status`

- [ ] **Task 1.6 — Seed Data & Migration** (Scope: XS)
  - Create seed migration for: initial branch records, default admin user (role=`admin`)
  - Verify all migrations are backward-compatible: nullable first → populate → constrain pattern (zero-downtime deployment)
  - Test Alembic upgrade from empty DB → verify all tables/enums/constraints → downgrade

### 2. Backend Tasks (FastAPI / Python 3.12+)

- [x] **Task 2.1 — Project Scaffolding & Configuration** (Scope: XS)
  - Initialize FastAPI project with Python 3.12+ async support
  - Configure project structure: `api/` (routers), `models/` (SQLAlchemy), `schemas/` (Pydantic), `services/` (business logic), `core/` (config, security), `workers/` (Celery tasks)
  - Set up dependency injection, `pydantic-settings` env config (dev/staging/production), CORS for CloudFront domain
  - Configure structured JSON logging with `correlation_id` middleware (tracing across API → queue → DB)
  - Set up SQLAlchemy async engine with connection pooling (AWS RDS)

- [x] **Task 2.2 — Authentication & RBAC Module** (Scope: M)
  - Implement JWT token generation (access + refresh tokens) with role claims (`patient`, `receptionist`, `doctor`, `manager`, `admin`, `executive`)
  - Implement `POST /api/v1/auth/login` (password-based for staff; placeholder for patient OTP flow)
  - Implement `POST /api/v1/auth/verify-request` (`phone_number` → enqueue OTP delivery via NotificationService)
  - Implement `POST /api/v1/auth/verify-code` (`phone_number` + `otp` → validate, issue JWT; invalidate prior active sessions)
  - Implement `POST /api/v1/auth/register` (patient self-registration: phone, email, password, profile details)
  - Implement FastAPI dependency `RoleChecker` for RBAC: enforce allowed roles per endpoint
  - Implement Redis rate limiting on OTP requests: max 3 verification requests per phone per 15 minutes; 10-min OTP TTL; max 5 attempts; single-use (`is_used=TRUE` after validation); new request invalidates prior active OTP
  - Business rules: invalidate prior active sessions on new OTP request; HTTP 429 on rate limit exceeded

- [ ] **Task 2.3 — Scheduling Engine — Doctor Availability** (Scope: M)
  - Implement `POST /api/v1/doctor-availability` (admin/manager creates shift blocks; access: `admin`, `manager`)
  - Implement `GET /api/v1/doctor-availability?doctor_id=&branch_id=&date=` (filtered query; access: `receptionist`, `doctor`, `manager`, `admin`)
  - Implement `PATCH /api/v1/doctor-availability/{id}` (update/cancel shift; access: `admin`, `manager`)
  - Implement cross-branch availability aggregation for patient-facing booking
  - Implement `GET /api/v1/appointments/available-slots?doctor_id=&branch_id=&date=` (returns open 30-min slots per doctor/branch; access: public with rate limiting)

- [x] **Task 2.4 — Scheduling Engine — Appointment Booking with Pessimistic Locking** (Scope: L)
  - Implement `POST /api/v1/appointments` with pessimistic lock sequence (FR-019):
    1. Patient penalty tier check (Tier 3 → block/require staff override FR-015)
    2. Lock `doctor_availability` row (`SELECT ... FOR UPDATE` on doctor_id + time overlap + `is_cancelled=FALSE`)
    3. Lock conflicting `appointments` rows (`SELECT ... FOR UPDATE` on doctor_id + time overlap + `status=booked`)
    4. Insert appointment if no conflict; rollback and return HTTP 409 if conflict
  - Implement `PATCH /api/v1/appointments/{id}` (reschedule — re-run full conflict check with pessimistic locks; access: `patient`, `receptionist`, `manager`)
  - Implement `DELETE /api/v1/appointments/{id}` with cancellation penalty logic (FR-012–FR-017):
    - Identify requester (clinic vs patient)
    - Exempt clinic-initiated cancellations (FR-017) and emergency cancellations (FR-016)
    - For patient cancellations: if <2h before appointment, log late cancellation incident
    - Count late cancellations/no-shows in rolling 90-day window
    - Update penalty tier: Tier 1 (1 incident) → Tier 2 (2-3 incidents) → Tier 3 (≥4 incidents)
    - Log action to `security_audit_logs` within same transaction
  - Implement `GET /api/v1/appointments/my` (patient's appointments; access: `patient`)
  - Implement `GET /api/v1/appointments/today?branch_id=` (daily schedule for staff; access: `receptionist`, `doctor`, `manager`)
  - Implement staff override endpoint for Tier 3 restricted patients (FR-015): log override to `security_audit_logs`
  - Implement emergency schedule override with audit log (FR-020; access: `admin`, `manager`)
  - Implement auto-flagging affected appointments on doctor shift cancellation (FR-021): enqueue notification tasks for all affected patients
  - **Status**: COMPLETE (2026-07-08) - SchedulingEngine with pessimistic locking, conflict detection, and penalty logic implemented

- [x] **Task 2.5 — Clinical Record Service with Encryption** (Scope: L)
  - Implement AWS KMS client (boto3) with envelope encryption:
    - `generate_data_key()` → returns plaintext DEK + encrypted DEK
    - `decrypt_data_key(encrypted_dek)` → returns plaintext DEK
    - DEK caching in application memory (reduce KMS API latency)
  - Implement AES-256-GCM encryption/decryption utility (Python `cryptography` library):
    - Encrypt: generate random 96-bit IV → encrypt with plaintext DEK → store IV + ciphertext + tag
    - Decrypt: extract IV → decrypt with plaintext DEK → verify tag
    - Probabilistic encryption: random IV per write prevents pattern analysis
  - Implement `POST /api/v1/clinical-records` (access: `doctor` only):
    - RBAC check: role must be `doctor`
    - Generate data key from KMS → encrypt notes/diagnosis/prescriptions → write to DB
    - Write audit log to `security_audit_logs` within same DB transaction (NFR-007)
    - HTTP 503 on KMS failure; clinical data never written in plaintext
  - Implement `GET /api/v1/clinical-records/patient/{patient_id}` (access: `doctor` only):
    - Fetch encrypted records from DB → decrypt DEK via KMS → decrypt fields in memory
    - Log every access to `security_audit_logs` (including cross-branch emergency reads — FR-007)
  - Implement `GET /api/v1/clinical-records/{appointment_id}` (access: `doctor` only; single record retrieval)
  - Implement KMS error handling: HTTP 503 on KMS unavailability; clinical data never written in plaintext
  - **Status**: COMPLETE (2026-07-09) - ClinicalRecordService with KMS envelope encryption, AES-256-GCM, audit logging implemented

- [ ] **Task 2.6 — Front Desk Operations** (Scope: S)
  - Implement `POST /api/v1/appointments/walk-in` (access: `receptionist`; registers walk-in + books immediate slot)
  - Implement `PATCH /api/v1/appointments/{id}/check-in` (access: `receptionist`; marks patient arrived; notifies doctor)
  - Implement `POST /api/v1/patients/register` (access: `receptionist`; creates patient profile + linked user account)

- [x] **Task 2.7 — NotificationService Abstraction & Async Workers** (Scope: M)
  - Implement Strategy Pattern interface: `NotificationService` abstract base class (INT-004)
  - Implement `WhatsAppCloudAPIClient` adapter (REST to WhatsApp Business Cloud API; primary channel)
  - Implement `TermiiSMSClient` adapter (REST to Termii gateway; primary Nigerian SMS with DND-bypass)
  - Implement `InfobipSMSClient` adapter (REST to Infobip gateway; secondary fallback SMS)
  - Implement failover orchestrator: try WhatsApp → on failure/timeout (15s) → Termii → on failure → Infobip
  - Implement Celery task definitions (async via Redis queue):
    - `send_appointment_confirmation(appointment_id)`
    - `send_appointment_reminder(appointment_id, type)` (24h and 2h reminders)
    - `send_cancellation_alert(appointment_id)`
    - `send_otp(verification_id)`
  - Implement idempotency tracking via `NotificationLog` table to prevent duplicate sends on retry
  - Implement notification scheduling for reminders (scheduled Celery tasks at 24h and 2h before appointment)
  - Configure Celery worker with Redis as broker
  - **Status**: COMPLETE (2026-07-08) - NotificationService with Strategy Pattern, failover chain, and Celery tasks implemented

- [x] **Task 2.8 — Management & Operational Reports** (Scope: M)
  - Implement `GET /api/v1/reports/branch/daily?branch_id=&date=` (access: `manager`; daily ops metrics: appointments, no-shows, utilization)
  - Implement `GET /api/v1/reports/branch/appointments?branch_id=&start_date=&end_date=` (access: `manager`; appointment analytics)
  - Implement `GET /api/v1/reports/organization/summary?start_date=&end_date=` (access: `executive`; cross-clinic aggregated metrics)
  - Implement `GET /api/v1/appointments/no-show-stats?period=30d` (access: `manager`; no-show trends for penalty analysis)
  - Implement `GET /api/v1/reports/notification-delivery?start_date=&end_date=` (access: `admin`; delivery success rates per provider from `NotificationLog`)
  - **Status**: COMPLETE (2026-07-09) - ReportService with branch/organization/notification delivery endpoints implemented

### 3. Frontend Tasks (Vite + React PWA / TypeScript)

- [ ] **Task 3.1 — Project Scaffolding & PWA Configuration** (Scope: S)
  - Initialize Vite + React + TypeScript project
  - Configure Workbox service worker: precache static shell (HTML/JS/CSS); runtime cache API responses with network-first strategy
  - Set up Dexie.js for IndexedDB: define schema for offline appointment cache (current-day appointments)
  - Configure PWA manifest (`manifest.json`): app name, icons (192x192, 512x512), theme colors, display mode (`standalone`)
  - Set up React Router: `/login`, `/register`, `/dashboard`, `/appointments`, `/clinical`, `/reports`, `/admin`
  - Configure Axios instance: base URL (API Gateway via custom domain), JWT interceptor (attach Bearer token, handle 401 redirect to login)
  - Set up Tailwind CSS for responsive design system (mobile/tablet/desktop)
  - Configure S3/CloudFront deployment scripts (build → upload → invalidation)

- [ ] **Task 3.2 — Authentication UI** (Scope: S)
  - Implement patient registration page (phone, email, password, profile details)
  - Implement OTP verification screen (phone input → 6-digit OTP code input → auto-submit)
  - Implement staff login page (email + password)
  - Implement password reset flow
  - Implement JWT token refresh logic (silent refresh on 401 using refresh token)
  - Implement role-based route guards (redirect unauthenticated/non-authorized users)

- [ ] **Task 3.3 — Patient Portal** (Scope: M)
  - Implement appointment booking flow: select branch → select doctor → pick available slot → confirm
  - Implement appointment list view (upcoming + past appointments)
  - Implement appointment detail view (show appointment info, cancellation/reschedule buttons)
  - Implement cancellation with confirmation dialog (show penalty warning for <2h cancellations per FR-012)
  - Implement reschedule flow (re-run slot selection for same doctor)
  - Implement patient profile view (view/edit personal details)
  - Implement lab results view (show only released results per FR-008)
  - Implement penalty tier awareness: warning banner for Tier 1, confirmation flow for Tier 2, block + prompt contact clinic for Tier 3 (FR-014)

- [ ] **Task 3.4 — Staff Dashboard (Receptionist)** (Scope: M)
  - Implement daily schedule view (filterable by branch, date — shows all appointments)
  - Implement check-in workflow (select appointment → mark patient arrived; notify doctor)
  - Implement walk-in registration UI (create patient + book immediate slot in one flow)
  - Implement phone booking UI (receptionist books on behalf of phone patient)
  - Implement offline mode: cache current-day appointments in IndexedDB; show "Offline Mode — Read Only" banner when disconnected (NFR-004)
  - Implement patient search (by name/phone/email)
  - Implement override booking for Tier 3 restricted patients (with admin override selection + audit log indication per FR-015)

- [ ] **Task 3.5 — Doctor Clinical Portal** (Scope: M)
  - Implement daily schedule view (shows today's booked appointments with patient info)
  - Implement appointment detail sidebar (patient profile summary, visit history)
  - Implement clinical note entry form:
    - Notes (text area) — encrypted client-side before submit
    - Diagnosis (text area) — encrypted
    - Prescriptions (text area) — encrypted
    - Lab results release toggle (FR-008)
  - Implement patient clinical history view (read-only previous records, decrypted in memory)
  - Implement lab results management (upload placeholder UI, mark as released)
  - Implement cross-branch emergency access flow (with explicit confirmation and audit log entry per FR-007)

- [ ] **Task 3.6 — Management Dashboard** (Scope: S)
  - Implement branch manager dashboard (daily appointments, no-shows, cancellation rate, utilization)
  - Implement senior manager dashboard (cross-clinic aggregated KPI cards, branch comparison charts)
  - Implement notification delivery dashboard (delivery success rate per provider, failure trends from `NotificationLog`)
  - Implement date range selector and export (CSV placeholder)
  - Implement real-time data refresh polling (30-second interval)

- [ ] **Task 3.7 — Admin Console** (Scope: S)
  - Implement branch management UI (CRUD branches)
  - Implement user management UI (create staff users, assign roles)
  - Implement doctor availability/blockout management UI (set recurring weekly schedules + exceptions)
  - Implement system settings (notification provider configuration, penalty thresholds)

- [ ] **Task 3.8 — Shared UI Components & Offline Infrastructure** (Scope: M)
  - Implement shared component library: DataTable, Form fields with validation, Modal/Dialog, Toast notifications, Loading skeletons, Empty states, Error boundaries
  - Implement IndexedDB sync manager (fetch daily schedule on login → store locally → serve from cache on disconnect)
  - Implement Service Worker lifecycle management (install → activate → fetch with network-first + cache fallback strategy)
  - Implement session expiry handling (purge IndexedDB on logout)
  - Implement network status indicator (online/offline banner)

### 4. Testing Tasks

- [x] **Task 4.1 — Unit Tests: Backend Services** (Scope: M)
  - Test `AuthenticationService`: JWT generation, token refresh, role extraction
  - Test `OTPService`: code generation, validation, rate limiting (3 req/15min), max attempts (5), expiry (10min), single-use
  - Test `SchedulingEngine`: slot validation, conflict detection, pessimistic lock behavior (`SELECT ... FOR UPDATE`)
  - Test `ClinicalRecordService`: encryption/decryption round-trip (AES-256-GCM), KMS key caching, error handling on KMS failure (HTTP 503)
  - Test `NotificationService`: Strategy Pattern routing, failover chain (WhatsApp → Termii → Infobip), idempotency via `NotificationLog`
  - Test `CancellationPenaltyEngine`: tier calculation (Tier 1/2/3), emergency exemption (FR-016), staff override (FR-015), rolling 90-day window
  - Test RBAC enforcement: each endpoint with valid/invalid roles; verify system admins CANNOT read clinical records (NFR-008)
  - **Status**: COMPLETE (2026-07-10) - All 173 tests pass; coverage at 67% (target 80%)
  - **Router Integration Tests**: 44 tests added for auth, appointments, and clinical_records endpoints

- [ ] **Task 4.2 — Integration Tests: API Endpoints** (Scope: M)
  - Auth flow: register → verify OTP (WhatsApp/SMS failover) → login → access protected endpoints → token refresh
  - Booking flow: create availability → book appointment → verify conflict detection with pessimistic locks (parallel requests) → reschedule → cancel with penalty tier update
  - Clinical records flow: create record (encrypt) → read record (decrypt) → cross-branch access → audit log verification
  - Notification flow: trigger notification → verify Celery task queued → verify provider fallback on failure → verify `NotificationLog` entry
  - Report endpoints: verify data aggregation accuracy, date filtering, branch filtering

- [ ] **Task 4.3 — Database & Migration Tests** (Scope: S)
  - Test Alembic migrations: upgrade from empty DB → verify all tables/enums/constraints → downgrade
  - Test pessimistic lock race condition: concurrent booking requests for same slot, verify exactly one succeeds (HTTP 201), others fail (HTTP 409)
  - Test clinical record encryption at rest: query `clinical_records` directly, verify ciphertext (no plaintext)
  - Test backward-compatible migration pattern: add nullable column → populate → add constraint

- [ ] **Task 4.4 — Frontend Tests** (Scope: S)
  - Test PWA offline capability: load dashboard → disconnect → verify cached appointments displayed (≥2h) → verify "Offline Mode — Read Only" banner → attempt write → verify blocked → reconnect → verify normal operation resumes
  - Test penalty tier UI: Tier 1 shows warning → Tier 2 shows confirmation → Tier 3 blocks booking
  - Test RBAC routing: patient cannot access staff routes, receptionist cannot access clinical routes, system admin cannot access clinical records (NFR-008)
  - Test responsive layout on mobile/tablet/desktop viewports

- [ ] **Task 4.5 — End-to-End Tests** (Scope: M)
  - Full patient journey: register → verify phone (OTP via WhatsApp/SMS failover) → book appointment → receive confirmation (WhatsApp/SMS) → cancel → verify penalty logged
  - Full doctor journey: view schedule → select appointment → write clinical notes (encrypted) → release lab results
  - Full receptionist journey: register walk-in → book slot → check-in patient → override Tier 3 restriction (with audit log)
  - Offline resilience: simulate network loss → verify read-only cache → restore connection → verify sync

- [ ] **Task 4.6 — Performance Tests** (Scope: S)
  - Verify `GET /api/v1/appointments/available-slots` response < 2.0s at 100 concurrent users (NFR-001)
  - Verify pessimistic lock acquisition completes within 3.0s transaction timeout
  - Verify PWA static assets load < 3.0s over simulated Nigerian 3G/4G (NFR-002) using Lighthouse

### 5. Deployment Tasks (AWS Infrastructure)

- [ ] **Task 5.1 — Infrastructure Setup** (Scope: M)
  - Configure AWS RDS PostgreSQL 16+ instance with automated backups and multi-AZ failover
  - Configure AWS ElastiCache Redis cluster for Celery broker + rate limiting counters
  - Configure AWS S3 bucket for PWA static assets with public read + versioning
  - Configure AWS CloudFront distribution with S3 origin, custom domain, TLS certificate
  - Configure AWS API Gateway with rate limiting, request validation, and CloudFront integration
  - Configure AWS KMS key with key policy scoped strictly to backend application IAM role (NFR-008); root/admin IAM roles explicitly denied
  - Set up IAM roles and policies: backend server role (`kms:Encrypt`/`kms:Decrypt`, RDS connect), worker role (same minus KMS)
  - Configure security groups: RDS access only from backend security group, Redis access only from backend + workers
  - Set up environment-based configuration (dev/staging/production) with AWS Secrets Manager for DB credentials

- [ ] **Task 5.2 — CI/CD Pipeline** (Scope: S)
  - Configure GitHub Actions CI pipeline: lint → test → build
  - Configure CD pipeline: deploy PWA to S3/CloudFront (cache invalidations), deploy FastAPI to AWS ECS Fargate or Elastic Beanstalk
  - Configure Alembic migration execution as separate deployment step (not auto-run on app start)
  - Configure CloudWatch/Datadog dashboards for API latency, error rates, DB query duration (alarm if >2.0s)

- [ ] **Task 5.3 — Staging Environment & Rollout** (Scope: S)
  - Deploy staging environment with identical architecture (smaller instance sizes)
  - Execute full end-to-end test suite against staging
  - Execute offline cache validation: simulate workstation disconnection tests (NFR-004)
  - Lighthouse audit: verify PWA score ≥90, accessibility ≥85
  - Phased clinic rollout plan: Branch A (Week 1) → Branch B (Week 3) → Branch C (Week 5)
  - Rollback plan: CloudFront points to previous S3 build version; RDS point-in-time recovery; Alembic downgrade scripts ready

- [ ] **Task 5.4 — Monitoring & Alerting Setup** (Scope: S)
  - Configure structured JSON logging with `correlation_id` across API → queue → DB
  - Set up CloudWatch alarms: DB connection pool >80%, API p95 latency >3.0s, 5xx error rate >1%, KMS throttling
  - Configure DB query duration monitoring with alert if search >2.0s (NFR-001)
  - Set up uptime monitoring for 99.9% availability Mon–Sat 07:00–20:00 WAT (NFR-003)
  - Configure notification delivery monitoring via `NotificationLog`: provider success rates, failover frequency

---

## Checkpoints & Verifications

- **Checkpoint 1 — Schema & Migrations Complete**: Alembic migrations apply cleanly from empty DB; all tables, enums, constraints, and indexes verified in PostgreSQL. Race condition test passes (concurrent bookings → exactly one succeeds).
- **Checkpoint 2 — Auth & RBAC Functional**: Patient registration → OTP verification (WhatsApp/SMS failover) → JWT issuance → role-protected endpoints enforce access correctly. Rate limiting verified (3 OTP requests/15min). System admins CANNOT read clinical records (NFR-008).
- **Checkpoint 3 — Booking Engine Verified**: Create doctor availability → book appointment → verify conflict detection with pessimistic locks → reschedule → cancel with penalty tier update → staff override on Tier 3 patient. Parallel booking test passes.
- **Checkpoint 4 — Clinical Encryption Verified**: Write clinical record → verify ciphertext in database (no plaintext) → read back decrypted content → verify audit log entry → cross-branch access logged as emergency → KMS unavailable returns HTTP 503. KMS audit trail shows all key usage.
- **Checkpoint 5 — Notification Failover Functional**: Trigger appointment confirmation → verify WhatsApp attempt → fail WhatsApp → verify Termii fallback → fail Termii → verify Infobip fallback. `NotificationLog` shows all attempts with provider, status, timestamps. Idempotency prevents duplicates.
- **Checkpoint 6 — PWA Offline Capability Verified**: Load dashboard → disconnect network → verify read-only appointment cache from IndexedDB (≥2h) → verify "Offline Mode — Read Only" banner → attempt write → verify blocked → reconnect → verify normal operation resumes. IndexedDB purged on logout.
- **Checkpoint 7 — Performance Benchmarks Met**: `GET /api/v1/appointments/available-slots` < 2.0s at 100 concurrent users (NFR-001). PWA page load < 3.0s on simulated 3G/4G (NFR-002) using Lighthouse. Pessimistic lock acquisition completes within 3.0s timeout.
- **Checkpoint 8 — Deployment & Rollout**: Staging environment green-lit with all E2E tests passing. Branch A live (Week 1). Branch B live (Week 3). Branch C live (Week 5). Rollback procedures validated.

---

## Risks and Constraints

| Risk | Impact | Mitigation |
|---|---|---|
| **Scheduling race condition bugs** | Double-bookings, data corruption | Pessimistic DB locks with `SELECT ... FOR UPDATE` in serializable transactions; verified via concurrent integration tests (FR-019) |
| **KMS misconfiguration or key compromise** | All clinical data inaccessible | IAM policies scoped strictly to backend role; key rotation policies; DEK caching with fallback on cache miss; CloudFormation templates with least-privilege key policies (NFR-008) |
| **WhatsApp API instability (Nigerian region)** | Notification delivery failure | Multi-provider failover chain (WhatsApp → Termii → Infobip); async retries via Celery; `NotificationLog` for delivery auditing and failover optimization (INT-001, INT-002, INT-003) |
| **Offline sync conflicts** | Stale read cache, write operations blocked | Read-only offline cache (≥2h); writes blocked with clear user messaging; push-based sync on reconnect (NFR-004) |
| **Migration backward-compatibility** | Production downtime during rollout | Nullable-first migration pattern; zero-downtime: add columns as nullable → populate → add constraint |
| **4-month timeline pressure** | Feature scope creep, quality degradation | Strict Phase 1 scope definition; no AI chatbot, no payment routing, no native apps; prioritized task sequencing |
| **Nigerian carrier DND policy changes** | SMS delivery failures | Dual domestic (Termii) + international (Infobip) SMS providers; ongoing monitoring of `NotificationLog` delivery rates (INT-002, INT-003) |
| **Multi-branch scheduling complexity (3→15 clinics)** | Performance degradation as scale increases | Indexed query patterns; connection pooling; load testing at 100 concurrent users; RDS read replicas for reporting queries if needed (NFR-001) |

---

## Appendix: Key API Contracts

### POST /api/v1/appointments
- **Access**: `patient`, `receptionist`, `manager`
- **Request**: `{ doctor_id, branch_id, start_datetime, end_datetime, booking_source }`
- **Response 201**: `{ appointment_id, status: "booked", payment_state: "pending" }`
- **Response 409**: Slot no longer available (lock contention)
- **Response 400**: Doctor not available at requested time

### POST /api/v1/clinical-records
- **Access**: `doctor` only
- **Request**: `{ appointment_id, patient_id, notes, diagnosis, prescriptions }`
- **Response 201**: `{ record_id, status: "encrypted_and_stored" }`
- **Behaviour**: Notes encrypted via AES-256-GCM before DB write; audit log written in same transaction (NFR-006, NFR-007)

### POST /api/v1/auth/verify-request
- **Access**: Public
- **Request**: `{ phone_number }`
- **Response 200**: `{ message: "We've sent a verification code to your phone" }`
- **Behaviour**: Enqueues OTP delivery task (WhatsApp-first, SMS fallback on 15s timeout); rate limited to 3 requests/15min

---

## Appendix: Data Model Reference (ERD Summary)

| Table | Classification | Key Fields |
|---|---|---|
| `users` | Auth (unencrypted) | `id` (PK), `phone_number` (UK), `email` (UK), `password_hash`, `role` |
| `patient_profiles` | Confidential (NDPR) | `id` (PK), `user_id` (FK), `full_name`, `date_of_birth`, `gender` |
| `doctor_availability` | Internal | `id` (PK), `doctor_id` (FK), `branch_id`, `start_datetime`, `end_datetime`, `is_cancelled` |
| `appointments` | Internal | `id` (PK), `doctor_id` (FK), `patient_id` (FK), `branch_id`, `start/end_datetime`, `status`, `payment_state`, `booking_source` |
| `clinical_records` | Restricted (Medical) — Encrypted | `id` (PK), `appointment_id` (FK), `patient_id` (FK), `doctor_id` (FK), `encrypted_notes`, `encrypted_diagnosis`, `encrypted_prescriptions`, `kms_key_version` |
| `verification_otps` | Internal | `id` (PK), `phone_number`, `hashed_otp`, `attempts`, `is_used`, `expires_at`, `delivery_channel` |
| `security_audit_logs` | Internal (Immutable) | `id` (PK), `user_id`, `action_type`, `patient_id`, `ip_address`, `timestamp`, `action_details` |
| `notifications_log` | Internal | `id` (PK), `recipient`, `delivery_type`, `provider`, `template_name`, `status`, `error_code`, `sent_at`, `delivery_attempts` |

**Key Relationships**:
- `users` 1 → 0..1 `patient_profiles`
- `users` 1 → 0..* `doctor_availability` (as doctor)
- `users` 1 → 0..* `appointments` (as doctor or patient)
- `appointments` 1 → 0..1 `clinical_records`
- `users` 1 → 0..* `clinical_records` (as author/subject)

---

## Appendix: UML Model References

| Diagram | Purpose | Key Elements |
|---|---|---|
| Class Diagram | Static entity domain model | `User`, `PatientProfile`, `DoctorAvailability`, `Appointment`, `ClinicalRecord`, `VerificationOTP`, `SecurityAuditLog` |
| Component Diagram | FastAPI backend decomposition | `API Route Controllers`, `Authentication & RBAC Manager`, `Scheduling Engine`, `Clinical Record Service`, `OTP Verification Engine`, `Notification Service Abstraction` |
| Sequence: Booking | Pessimistic locking flow | Concurrent `SELECT ... FOR UPDATE`; HTTP 201 vs HTTP 409 |
| Sequence: OTP | Multi-gateway failover | WhatsApp → Termii → Infobip with 15s timeout |
| Sequence: Clinical | Encryption & audit logging | KMS GenerateDataKey → AES-256-GCM encrypt → DB write + audit log in same transaction |
| State: Appointment | Status transitions | `Booked` → `Cancelled`/`Completed`/`NoShow` with payment states |
| State: Penalty | Tier progression | `Normal` → `Tier1` → `Tier2` → `Tier3` with rolling 90-day decay |
| Activity: Booking | Control flow with penalty checks | Tier check → availability → lock → conflict check → create → notify |
| Activity: Cancellation | Penalty engine flow | Requester ID → time check → emergency exemption → incident count → tier update |

---

## Appendix: Assumptions & Dependencies

| Assumption | Dependency |
|---|---|
| Patients have active mobile data access to load lightweight PWA | Affordable mobile data in Nigeria |
| WhatsApp Business Cloud API provides reliable delivery in Nigeria | Meta/WhatsApp API availability |
| Local power outages mitigated by clinic generators/UPS | Clinic infrastructure |
| Medical staff will adopt digital note entry | Change management / training |
| Termii DND-bypass works for MTN/Airtel/Glo/9mobile | Nigerian carrier routing policies |
| AWS KMS available in target region (e.g., `af-south-1`) | AWS service availability |

---

## Appendix: Phase 2 Roadmap (Deferred)

| Feature | Rationale for Phase 2 |
|---|---|
| AI Chatbot (AI-001–AI-004) | LLM integration requires Python ecosystem maturity; Phase 1 focuses on core scheduling |
| Paystack/Flutterwave payment routing (INT-005) | DB schema supports payment states; routing logic deferred to reduce Phase 1 scope |
| Native Android/iOS apps | Responsive web PWA satisfies mobile needs; native apps add cost/complexity |
| Video/audio telemedicine | Not in SRD v1.3; requires additional infrastructure and regulatory compliance |
| Semantic/vector search for AI scheduling | pgvector extension installed in Phase 1; AI search queries deferred to Phase 2 |