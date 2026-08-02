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

- [x] **Task 1.4 — Clinical Records Schema** (Scope: S)
  - Create `clinical_records` table: `id` (UUID PK), `appointment_id` (UUID UNIQUE FK → appointments, RESTRICT DELETE), `patient_id` (UUID FK → users, RESTRICT DELETE), `doctor_id` (UUID FK → users, RESTRICT DELETE), `encrypted_notes` (TEXT, AES-256-GCM ciphertext), `encrypted_diagnosis` (TEXT, AES-256-GCM ciphertext), `encrypted_prescriptions` (TEXT, AES-256-GCM ciphertext), `kms_key_version` (VARCHAR(100)), `created_at` (TIMESTAMPTZ)
  - Create `security_audit_logs` table: `id` (UUID PK), `user_id` (UUID, NO FK for immutability), `action_type` (VARCHAR(100): `READ_CLINICAL_RECORD`, `WRITE_CLINICAL_RECORD`, `OVERRIDE_BOOKING`, etc.), `patient_id` (UUID), `ip_address` (VARCHAR(45)), `timestamp` (TIMESTAMPTZ, default CURRENT_TIMESTAMP), `action_details` (TEXT)
  - CRITICAL: All clinical columns store ciphertext only; decryption only in application memory for authenticated `doctor` role users (NFR-006, NFR-008)
  - Create indexes: `clinical_records.patient_id`, `clinical_records.doctor_id`, `security_audit_logs.user_id + timestamp`

- [x] **Task 1.5 — Notification & Supporting Schema** (Scope: XS)
  - Create `notifications_log` table: `id` (UUID PK), `recipient` (VARCHAR(255)), `delivery_type` (VARCHAR(20): `whatsapp`/`sms`), `provider` (VARCHAR(50): `whatsapp`/`termii`/`infobip`), `template_name` (VARCHAR(100)), `status` (VARCHAR(50)), `error_code` (VARCHAR(100)), `sent_at` (TIMESTAMPTZ), `delivery_attempts` (INTEGER)
  - Create indexes: `notifications_log.recipient + sent_at`, `notifications_log.provider + status`

- [x] **Task 1.6 — Seed Data & Migration** (Scope: XS)
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

- [x] **Task 2.3 — Scheduling Engine — Doctor Availability** (Scope: M)
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

- [x] **Task 2.6 — Front Desk Operations** (Scope: S)
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

- [x] **Task 3.1 — Project Scaffolding & PWA Configuration** (Scope: S)
  - Initialize Vite + React + TypeScript project
  - Configure Workbox service worker: precache static shell (HTML/JS/CSS); runtime cache API responses with network-first strategy
  - Set up Dexie.js for IndexedDB: define schema for offline appointment cache (current-day appointments)
  - Configure PWA manifest (`manifest.json`): app name, icons (192x192, 512x512), theme colors, display mode (`standalone`)
  - Set up React Router: `/login`, `/register`, `/dashboard`, `/appointments`, `/clinical`, `/reports`, `/admin`
  - Configure Axios instance: base URL (API Gateway via custom domain), JWT interceptor (attach Bearer token, handle 401 redirect to login)
  - Set up Tailwind CSS for responsive design system (mobile/tablet/desktop)
  - Configure S3/CloudFront deployment scripts (build → upload → invalidation)

- [x] **Task 3.2 — Authentication UI** (Scope: S)
  - Implement patient registration page (phone, email, password, profile details)
  - Implement OTP verification screen (phone input → 6-digit OTP code input → auto-submit)
  - Implement staff login page (email + password)
  - Implement password reset flow
  - Implement JWT token refresh logic (silent refresh on 401 using refresh token)
  - Implement role-based route guards (redirect unauthenticated/non-authorized users)

- [x] **Task 3.3 — Patient Portal** (Scope: M)
  - Implement appointment booking flow: select branch → select doctor → pick available slot → confirm
  - Implement appointment list view (upcoming + past appointments)
  - Implement appointment detail view (show appointment info, cancellation/reschedule buttons)
  - Implement cancellation with confirmation dialog (show penalty warning for <2h cancellations per FR-012)
  - Implement reschedule flow (re-run slot selection for same doctor)
  - Implement patient profile view (view/edit personal details)
  - Implement lab results view (show only released results per FR-008)
  - Implement penalty tier awareness: warning banner for Tier 1, confirmation flow for Tier 2, block + prompt contact clinic for Tier 3 (FR-014)

- [x] **Task 3.4 — Staff Dashboard (Receptionist)** (Scope: M)
  - Implement daily schedule view (filterable by branch, date — shows all appointments)
  - Implement check-in workflow (select appointment → mark patient arrived; notify doctor)
  - Implement walk-in registration UI (create patient + book immediate slot in one flow)
  - Implement phone booking UI (receptionist books on behalf of phone patient)
  - Implement offline mode: cache current-day appointments in IndexedDB; show "Offline Mode — Read Only" banner when disconnected (NFR-004)
  - Implement patient search (by name/phone/email)
  - Implement override booking for Tier 3 restricted patients (with admin override selection + audit log indication per FR-015)

- [x] **Task 3.5 — Doctor Clinical Portal** (Scope: M)
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

- [x] **Task 3.6 — Management Dashboard** (Scope: S)
  - Implement branch manager dashboard (daily appointments, no-shows, cancellation rate, utilization)
  - Implement senior manager dashboard (cross-clinic aggregated KPI cards, branch comparison charts)
  - Implement notification delivery dashboard (delivery success rate per provider, failure trends from `NotificationLog`)
  - Implement date range selector and export (CSV placeholder)
  - Implement real-time data refresh polling (30-second interval)

- [x] **Task 3.7 — Admin Console** (Scope: S)
  - Implement branch management UI (CRUD branches)
  - Implement user management UI (create staff users, assign roles)
  - Implement doctor availability/blockout management UI (set recurring weekly schedules + exceptions)
  - Implement system settings (notification provider configuration, penalty thresholds)

- [x] **Task 3.8 — Shared UI Components & Offline Infrastructure** (Scope: M)
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

- [x] **Task 4.2 — Integration Tests: API Endpoints** (Scope: M)
  - Auth flow: register → verify OTP (WhatsApp/SMS failover) → login → access protected endpoints → token refresh
  - Booking flow: create availability → book appointment → verify conflict detection with pessimistic locks (parallel requests) → reschedule → cancel with penalty tier update
  - Clinical records flow: create record (encrypt) → read record (decrypt) → cross-branch access → audit log verification
  - Notification flow: trigger notification → verify Celery task queued → verify provider fallback on failure → verify `NotificationLog` entry
  - Report endpoints: verify data aggregation accuracy, date filtering, branch filtering

- [x] **Task 4.3 — Database & Migration Tests** (Scope: S)
  - Test Alembic migrations: upgrade from empty DB → verify all tables/enums/constraints → downgrade
  - Test pessimistic lock race condition: concurrent booking requests for same slot, verify exactly one succeeds (HTTP 201), others fail (HTTP 409)
  - Test clinical record encryption at rest: query `clinical_records` directly, verify ciphertext (no plaintext)
  - Test backward-compatible migration pattern: add nullable column → populate → add constraint

- [x] **Task 4.4 — Frontend Tests** (Scope: S)
  - Test PWA offline capability: load dashboard → disconnect → verify cached appointments displayed (≥2h) → verify "Offline Mode — Read Only" banner → attempt write → verify blocked → reconnect → verify normal operation resumes
  - Test penalty tier UI: Tier 1 shows warning → Tier 2 shows confirmation → Tier 3 blocks booking
  - Test RBAC routing: patient cannot access staff routes, receptionist cannot access clinical routes, system admin cannot access clinical records (NFR-008)
  - Test responsive layout on mobile/tablet/desktop viewports

- [x] **Task 4.5 — End-to-End Tests** (Scope: M)
  - Full patient journey: register → verify phone (OTP via WhatsApp/SMS failover) → book appointment → receive confirmation (WhatsApp/SMS) → cancel → verify penalty logged
  - Full doctor journey: view schedule → select appointment → write clinical notes (encrypted) → release lab results
  - Full receptionist journey: register walk-in → book slot → check-in patient → override Tier 3 restriction (with audit log)
  - Offline resilience: simulate network loss → verify read-only cache → restore connection → verify sync

- [x] **Task 4.6 — Performance Tests** (Scope: S)
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

---

## Feature Addition: Email-based Patient Registration with Auth Email and Separate Patient/Staff Login

**Scenario**: Feature Addition / System Evolution (Scenario 2)
**Architecture Decision**: ARCHITECTURE CHANGE REQUIRED (see architecture-decision.md)
**ADRs**: ADR-005 (NEW - required before implementation), ADR-001, ADR-002, ADR-004 (Existing)
**Target Phase**: Phase 1 - New email-based registration alongside existing OTP system (backward compatible)

### Overview

This plan implements email-based patient registration with authentication email delivery and a separate patient/staff login flow. The feature is built alongside the existing phone+OTP system (Phase 1), enabling backward-compatible introduction of the new flow.

**Target Outcome**: Patients can register using email + phone, receive an authentication email with a password creation link, set their password, and log in via a separate patient login endpoint - all while staff login remains unchanged on the existing email+password flow.

**Phased Approach**:

- **Phase 1** (This plan): New email-based registration alongside existing OTP system (backward compatible)
- **Phase 2**: Migrate existing patients to new system
- **Phase 3**: Deprecate OTP-based patient auth

### Architecture Decisions

| Reference | Decision | Impact |
| --- | --- | --- |
| ADR-005 (NEW) | Email-based Patient Registration Architecture | Required before implementation - must cover database separation strategy, email provider integration, password policy, auth token strategy, JWT differentiation |
| architecture-decision.md | Logical separation within same database (recommended) | Avoids cross-database complexity; same PostgreSQL instance, separate auth tables, different JWT claims |
| architecture-decision.md | New ADR-005 required | Triggers sync rules: new_provider_or_integration and architecture_change |
| ADR-004 (Existing) | Pluggable NotificationService with Strategy Pattern | Email notification delivery integrated as a new provider adapter |
| ADR-001 (Existing) | PostgreSQL 16+ as primary datastore | Schema changes via Alembic migrations; email_verification_tokens table added |
| ADR-002 (Existing) | React PWA with Vite | New frontend pages (registration with email, password creation, patient login) |

#### Key Technical Decisions

1. **Database Strategy**: Logical separation within the same PostgreSQL database. Patients and staff share the same database instance but use different tables (existing users + new email_verification_tokens) and different JWT claim audiences.
2. **Email Provider**: Email notification capability added as a new adapter in the existing NotificationService Strategy Pattern (ADR-004). Provider selection (SMTP/SendGrid/AWS SES) to be documented in ADR-005.
3. **Password Policy**: Minimum 8 characters, at least 1 uppercase, 1 lowercase, 1 digit, 1 special character. Server-side validation enforced.
4. **Auth Token Strategy**: Cryptographically random tokens (secrets.token_urlsafe(32)); 60-minute TTL; single-use (invalidated after password creation); stored as bcrypt hash in email_verification_tokens table.
5. **JWT Token Differentiation**: Patient tokens include aud: "patient" claim; staff tokens include aud: "staff" claim. This enables separate validation paths and prevents token type confusion.
6. **Rate Limiting**: Email verification requests limited to 3 requests per email per 15 minutes (matching existing OTP rate limit pattern).

### Task List

#### 0. Pre-Implementation Tasks (SSOT & ADR)

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

#### 1. Database Tasks

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

#### 2. Backend Tasks

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

#### 3. Frontend Tasks

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

#### 4. Testing Tasks

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

#### 5. Deployment Tasks

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

### Checkpoints & Verifications

- **Checkpoint 0 — ADR-005 Approved**: ADR-005 document created and approved; SSOT artifacts updated to reflect new architecture. Required before any implementation begins.
- **Checkpoint 1 — Schema Migrations Complete**: `email_verification_tokens` table created; `is_email_verified` column added to `users`; Alembic upgrade/downgrade works cleanly. All existing data preserved.
- **Checkpoint 2 — Email Registration Flow Functional**: `POST /api/v1/auth/patient/register` creates verification token, enqueues email task. `POST /api/v1/auth/patient/verify-email` validates token, enforces password policy, creates user, returns JWT. `POST /api/v1/auth/patient/login` authenticates with email+password. Rate limiting enforced (3/15min).
- **Checkpoint 3 — Login Separation Verified**: Patient login at `/api/v1/auth/patient/login` returns JWT with `aud: "patient"`. Staff login at `/api/v1/auth/login` returns JWT with `aud: "staff"`. Patient JWT cannot access staff endpoints. Staff JWT cannot access patient endpoints. Existing OTP endpoints still functional with deprecation headers.
- **Checkpoint 4 — Frontend Flow Complete**: Patient registration page with email input → password creation page with token → patient login page → patient dashboard. Staff login page unchanged with patient link. Route guards enforce audience separation.
- **Checkpoint 5 — Email Delivery Verified**: Auth email sent with verification link. Link works (creates password). Expired link returns appropriate error. Resend functionality works. Rate limiting enforced. `NotificationLog` tracks all email attempts.
- **Checkpoint 6 — All Tests Pass**: Unit tests (token service, JWT differentiation, email provider) pass. Integration tests (full registration flow, login separation, rate limiting, resend) pass. Frontend tests (registration page, password creation, route guards) pass. E2E tests (full patient journey, full staff journey, cross-boundary) pass.

### Risks and Constraints

| Risk | Impact | Mitigation |
| --- | --- | --- |
| **Email deliverability issues (Nigerian ISPs)** | Auth emails not received → patients cannot complete registration | Multiple email provider options (SMTP/SendGrid/SES); SPF/DKIM/DMARC configuration; `NotificationLog` monitoring; resend endpoint for recovery |
| **Token interception in email** | Account takeover if verification link intercepted | Short TTL (60 min); single-use token; bcrypt-hashed token storage; HTTPS-only links |
| **Backward compatibility with OTP system** | Existing patients with OTP-only accounts lose access | Phase 1 keeps OTP system fully functional; Phase 2 migration plan; deprecation headers on old endpoints |
| **Password policy friction** | Patients abandon registration due to strict password rules | Clear password requirements displayed on creation page; strength indicator; balance between security and UX |
| **Rate limiting false positives** | Legitimate users blocked from resending verification | 15-minute window with 3-request limit matches existing OTP pattern; clear error message with retry-after header |
| **JWT audience claim enforcement gaps** | Token type confusion — patient token used for staff actions | Centralized `RoleChecker` dependency with audience validation; comprehensive integration tests; audit logging for cross-boundary access attempts |
| **Email provider API throttling** | Bulk email sends delayed | Celery async queue for email delivery; exponential backoff on provider throttling; failover to secondary email provider if configured |
| **SSOT synchronization debt** | Architecture drift if SSOT not updated concurrently | Task 0.2 enforces pre-implementation SSOT update; post-implementation sync required per `ssot.yaml` sync rules |

### Appendix: Affected Files & Artifacts

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