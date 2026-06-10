# Implementation Plan: Clinic Modernization Platform (CMP)

## Overview
The Clinic Modernization Platform (CMP) is a secure, decoupled clinic management system built with Vite + React on the frontend and FastAPI on the backend, targeting a chain of three private healthcare clinics in Nigeria. It features a Progressive Web App (PWA) shell for offline schedule viewing (resilient up to 2 hours), concurrent doctor-slot booking protected by relational database pessimistic locking, application-level medical record column encryption (via AES-256-GCM and AWS KMS), and a multi-channel message delivery engine (WhatsApp-first with SMS fallback) for patient verification OTPs.

## Architecture Decisions
- **Relational Database with Pessimistic Locking (PostgreSQL 16+)**: Selected to enforce strict database-level concurrency control (`SELECT ... FOR UPDATE`) to prevent double-booking of doctors across clinics.
- **Decoupled Vite + React PWA Frontend**: Provides sub-3.0s load times over Nigerian 3G/4G networks and utilizes Dexie.js (IndexedDB wrapper) with Workbox to store a 2-hour offline read-only scheduling cache.
- **Application-Level Column Encryption (AES-256-GCM + AWS KMS)**: Encrypts clinical notes, diagnoses, and prescriptions in the FastAPI server before storage. AWS KMS key policies restrict decrypt operations to the application server's execution role, excluding database and cloud admins.
- **Asynchronous Messaging Queue with Failover Gateway (Celery/Redis)**: Abstracts physical SMS/WhatsApp gateways. OTPs are sent via WhatsApp Cloud API first, and if delivery status fails or times out within 15 seconds, automatically falls back to Termii (with Nigerian DND-override) or Infobip SMS.
- **Role-Based Access Control & Auditing (FastAPI Scopes + PostgreSQL)**: Restricts access to sensitive endpoints and records all clinical read/write operations in an immutable, database-level security audit trail.

---

## Task List

### Phase 1: Foundation
- [ ] [Task 1: Repository Structure & Boilerplate Setup](#task-1-repository-structure--boilerplate-setup)
- [ ] [Task 2: Database Connection & Alembic Setup](#task-2-database-connection--alembic-setup)
- [ ] [Task 3: Base Database Models (Users & Patient Profiles)](#task-3-base-database-models-users--patient-profiles)
- [ ] [Task 4: JWT Authentication and Route Security Guard](#task-4-jwt-authentication-and-route-security-guard)
- [ ] [Task 5: Frontend Shell, Router & Local Database Setup](#task-5-frontend-shell-router--local-database-setup)

#### Checkpoint: Foundation
- [ ] Backend FastAPI application initializes successfully.
- [ ] Database connection pooling and Alembic run clean migrations.
- [ ] Frontend builds, router resolves basic pages, and Dexie.js schema initiates.
- [ ] Local tests run successfully: `pytest backend/tests/unit`

---

### Phase 2: Core Features
- [ ] [Task 6: Verification OTP Schema & Business Logic](#task-6-verification-otp-schema--business-logic)
- [ ] [Task 7: Notification Service Interface and Client Adapters](#task-7-notification-service-interface-and-client-adapters)
- [ ] [Task 8: Celery/Redis Worker Queue and OTP Delivery Failover](#task-8-celeryredis-worker-queue-and-otp-delivery-failover)
- [ ] [Task 9: Patient Registration UI & OTP Verification Flow](#task-9-patient-registration-ui--otp-verification-flow)
- [ ] [Task 10: Doctor Availability and Appointment Schemas](#task-10-doctor-availability-and-appointment-schemas)
- [ ] [Task 11: Concurrency-Safe Appointment Booking Endpoint](#task-11-concurrency-safe-appointment-booking-endpoint)
- [ ] [Task 12: Appointment Booking UI and Offline Cache](#task-12-appointment-booking-ui-and-offline-cache)
- [ ] [Task 13: Clinical Records Database Schema & Encryption Layer](#task-13-clinical-records-database-schema--encryption-layer)
- [ ] [Task 14: Clinical Consultation Endpoints & Audit Logging](#task-14-clinical-consultation-endpoints--audit-logging)
- [ ] [Task 15: Doctor Consultation Dashboard UI](#task-15-doctor-consultation-dashboard-ui)

#### Checkpoint: Core Features
- [ ] Patient registration with OTP verification (and fallback to Termii/Infobip SMS) is fully operational.
- [ ] Concurrent booking attempts on the same time slot correctly block the second request with an HTTP 409 status code.
- [ ] Offline synchronization caches schedules for 2 hours, showing an offline banner when network drops.
- [ ] Clinical records are stored fully encrypted in the database, with decryption only available to authorized doctor sessions.
- [ ] Audit logs write records to `security_audit_logs` inside the same database transaction.

---

### Phase 3: Extended Features, Polish & Deployment Prep
- [ ] [Task 16: Cancellation Rules & Penalty Checks](#task-16-cancellation-rules--penalty-checks)
- [ ] [Task 17: Front Desk Queue Board & Check-in UI](#task-17-front-desk-queue-board--check-in-ui)
- [ ] [Task 18: Manager Dashboard & Report Generation](#task-18-manager-dashboard-and-report-generation)
- [ ] [Task 19: Security Scanning, Optimization & Polish](#task-19-security-scanning-optimization--polish)

#### Checkpoint: Complete
- [ ] All features (cancellation penalties, front desk arrival board, metrics reporting) work end-to-end.
- [ ] Security scanners (bandit, safety, npm audit) return clean reports.
- [ ] Ready for rollout at the first pilot clinic.

---

## Detailed Task Definitions

### Phase 1: Foundation

#### Task 1: Repository Structure & Boilerplate Setup
**Description:** Configure workspace directories, setup Python backend package configurations using FastAPI, configure npm/Vite on the React frontend, and initialize development environment scripts.

**Acceptance criteria:**
- [ ] Backend runs with FastAPI + Uvicorn boilerplate on python 3.12+.
- [ ] Frontend initializes with Vite + React + TypeScript + vanilla CSS.
- [ ] Code formatting and linting rules configured (ruff for python, eslint/prettier for frontend).

**Verification:**
- [ ] Backend runs via `uvicorn src.main:app --reload`
- [ ] Frontend runs via `npm run dev`
- [ ] Lint check passes: `ruff check .` (backend) and `npm run lint` (frontend)

**Dependencies:** None

**Files likely touched:**
- `backend/pyproject.toml`
- `backend/src/main.py`
- `frontend/package.json`
- `frontend/vite.config.ts`

**Estimated scope:** Small: 1-2 files

---

#### Task 2: Database Connection & Alembic Setup
**Description:** Establish connection pooling with SQLAlchemy and configure the Alembic database migrations framework for PostgreSQL.

**Acceptance criteria:**
- [ ] Database helper file initializes SQLAlchemy engine with connection pool parameters (max 20 connections, 30s timeout).
- [ ] Alembic environment reads models dynamically to autogenerate migration scripts.
- [ ] Basic health-check endpoint verifies database connectivity.

**Verification:**
- [ ] Alembic migration initializes database: `alembic upgrade head`
- [ ] Health-check endpoint `/api/v1/health` returns SQL connection status: `"healthy"`

**Dependencies:** Task 1

**Files likely touched:**
- `backend/src/core/database.py`
- `backend/alembic/env.py`
- `backend/alembic.ini`
- `backend/src/main.py`

**Estimated scope:** Small: 1-2 files

---

#### Task 3: Base Database Models (Users & Patient Profiles)
**Description:** Implement database schemas for Users and Patient Profiles to support registration, user routing, and NDPR-compliant profile storage.

**Acceptance criteria:**
- [ ] `users` table created with hashed passwords, distinct roles (`patient`, `receptionist`, `doctor`, `manager`, `admin`, `executive`), and phone/email unique constraints.
- [ ] `patient_profiles` table linked to `users` via 1-to-1 relationship.
- [ ] Database migration successfully generates and executes tables.

**Verification:**
- [ ] Alembic autogenerates and applies migration: `alembic revision --autogenerate -m "create_user_and_profile_tables" && alembic upgrade head`
- [ ] Unit tests pass: `pytest backend/tests/unit/test_user_models.py`

**Dependencies:** Task 2

**Files likely touched:**
- `backend/src/models/user.py`
- `backend/tests/unit/test_user_models.py`
- `backend/alembic/versions/`

**Estimated scope:** Small: 1-2 files

---

#### Task 4: JWT Authentication and Route Security Guard
**Description:** Setup backend JWT generation, validation, and role-based access control (RBAC) scopes using FastAPI dependency injection.

**Acceptance criteria:**
- [ ] Password hashing utility enforces bcrypt/argon2 hashing.
- [ ] JWT tokens include user ID, role, and expiration (1 hour default).
- [ ] Scoped security dependencies block unauthorized client calls with HTTP 401/403.

**Verification:**
- [ ] Tests verify token generation and role verification: `pytest backend/tests/unit/test_auth.py`
- [ ] Contract tests check token schema: `pytest backend/tests/contract/test_auth.py`

**Dependencies:** Task 3

**Files likely touched:**
- `backend/src/core/auth.py`
- `backend/src/api/deps.py`
- `backend/tests/unit/test_auth.py`
- `backend/tests/contract/test_auth.py`

**Estimated scope:** Medium: 3-5 files

---

#### Task 5: Frontend Shell, Router & Local Database Setup
**Description:** Create Vite SPA structure including page router, styling stylesheets, and client IndexedDB configuration via Dexie.js for offline availability.

**Acceptance criteria:**
- [ ] React Router DOM routes set up for basic pages (Login, Register, Dashboard).
- [ ] CSS design tokens mapped (colors, typography, spacing).
- [ ] Dexie.js database initialized with schemas matching users, appointments, and shifts.

**Verification:**
- [ ] Frontend builds without TypeScript or bundling warnings: `npm run build`
- [ ] Browser console verifies Dexie.js initializes IndexedDB database `CMP_Local_Store`.

**Dependencies:** Task 1

**Files likely touched:**
- `frontend/src/main.tsx`
- `frontend/src/index.css`
- `frontend/src/services/db.ts`
- `frontend/src/services/api.ts`

**Estimated scope:** Medium: 3-5 files

---

### Phase 2: Core Features

#### Task 6: Verification OTP Schema & Business Logic
**Description:** Create the verification OTP table schema and implement generation, hashing, rate limiting, and consumption logic.

**Acceptance criteria:**
- [ ] `verification_otps` table contains phone, hashed OTP, attempts counter, is_used flag, delivery channel, and expires_at timestamp.
- [ ] Only one active OTP allowed per phone number (generating a new OTP invalidates previous active ones).
- [ ] Rate limits prevent more than 3 OTP requests per number in 15 minutes, and OTP is locked after 5 verification attempts.

**Verification:**
- [ ] Unit tests verify single-use constraints, rate limiting, and expiry: `pytest backend/tests/unit/test_otp.py`

**Dependencies:** Task 3, Task 4

**Files likely touched:**
- `backend/src/models/otp.py`
- `backend/src/services/otp_service.py`
- `backend/tests/unit/test_otp.py`

**Estimated scope:** Small: 1-2 files

---

#### Task 7: Notification Service Interface and Client Adapters
**Description:** Write the strategy-based `NotificationService` interface and implement HTTP client adapters for WhatsApp Business Cloud API, Termii SMS, and Infobip.

**Acceptance criteria:**
- [ ] Pluggable notification service interface allows injection of provider adapters.
- [ ] WhatsApp client handles template payloads and returns delivery status.
- [ ] Termii client adapts OTP templates to Termii API endpoints; Infobip handles fallback SMS.

**Verification:**
- [ ] Unit tests mock HTTP requests and verify correct payload structures for all three providers: `pytest backend/tests/unit/test_notifications.py`

**Dependencies:** Task 1

**Files likely touched:**
- `backend/src/services/notifications.py`
- `backend/src/services/whatsapp.py`
- `backend/src/services/termii.py`
- `backend/src/services/infobip.py`

**Estimated scope:** Medium: 3-5 files

---

#### Task 8: Celery/Redis Worker Queue and OTP Delivery Failover
**Description:** Setup Celery task processing with Redis backend to execute the WhatsApp-first OTP delivery with automatic 15-second SMS fallback.

**Acceptance criteria:**
- [ ] Async Celery task receives OTP code and phone number.
- [ ] Task triggers WhatsApp Cloud API. If error returned or delivery webhook is not confirmed within 15 seconds, automatically routes through Termii SMS, and finally Infobip as tertiary backup.
- [ ] Failovers are logged with high-resolution logs.

**Verification:**
- [ ] Integration tests verify delivery pipeline failover progression (simulating WhatsApp timeouts): `pytest backend/tests/integration/test_otp_failover.py`

**Dependencies:** Task 6, Task 7

**Files likely touched:**
- `backend/src/core/queue.py`
- `backend/src/tasks/notification_tasks.py`
- `backend/tests/integration/test_otp_failover.py`

**Estimated scope:** Medium: 3-5 files

---

#### Task 9: Patient Registration UI & OTP Verification Flow
**Description:** Implement client screens and API endpoints for user registration, linking registration with the OTP failover worker, and completing verification.

**Acceptance criteria:**
- [ ] API routes `POST /api/v1/auth/register` and `POST /api/v1/auth/verify` implemented.
- [ ] Registration form prompts for details; on submit, OTP is enqueued and user is directed to the OTP validation screen.
- [ ] Entering correct code authenticates user, sets JWT cookie/local storage, and redirects to Dashboard.

**Verification:**
- [ ] API integration tests run successfully: `pytest backend/tests/integration/test_auth_flow.py`
- [ ] Manual check: registering a user triggers the OTP task, submitting the correct OTP unlocks the dashboard.

**Dependencies:** Task 5, Task 8

**Files likely touched:**
- `backend/src/api/auth.py`
- `frontend/src/pages/Register.tsx`
- `frontend/src/pages/VerifyOTP.tsx`

**Estimated scope:** Medium: 3-5 files

---

#### Task 10: Doctor Availability and Appointment Schemas
**Description:** Create database tables and migration files for Doctor Shifts (`doctor_availability`) and Appointments.

**Acceptance criteria:**
- [ ] `doctor_availability` table records branch, doctor ID, start, end, and cancellation status (contains check constraint start < end).
- [ ] `appointments` table stores status enum, payment status enum, branch, start, end, booking source, doctor ID, and patient ID.
- [ ] Alembic migration successfully updates database tables.

**Verification:**
- [ ] Run migration: `alembic upgrade head`
- [ ] Verify database schema using SQL viewer or CLI tests: `pytest backend/tests/unit/test_scheduling_models.py`

**Dependencies:** Task 3

**Files likely touched:**
- `backend/src/models/scheduling.py`
- `backend/alembic/versions/`
- `backend/tests/unit/test_scheduling_models.py`

**Estimated scope:** Small: 1-2 files

---

#### Task 11: Concurrency-Safe Appointment Booking Endpoint
**Description:** Implement booking API with row-level pessimistic locking (`SELECT ... FOR UPDATE` via SQLAlchemy `with_for_update()`) to prevent slot double-bookings.

**Acceptance criteria:**
- [ ] API `POST /api/v1/appointments` locks doctor shift records in a transaction block.
- [ ] Checks for conflicting appointments; overlapping bookings on the locked rows fail with HTTP 409 (Conflict).
- [ ] Booking transactions complete or time out after 3.0s (preventing deadlocks).

**Verification:**
- [ ] Concurrent tests execute 10 simultaneous requests for the exact same slot; verify exactly 1 succeeds and 9 fail with 409: `pytest backend/tests/integration/test_booking_concurrency.py`

**Dependencies:** Task 4, Task 10

**Files likely touched:**
- `backend/src/services/booking.py`
- `backend/src/api/appointments.py`
- `backend/tests/integration/test_booking_concurrency.py`

**Estimated scope:** Medium: 3-5 files

---

#### Task 12: Appointment Booking UI and Offline Cache
**Description:** Build booking page and setup service worker caching (Workbox) to sync daily schedules to Dexie.js, allowing 2-hour offline read-only dashboard access.

**Acceptance criteria:**
- [ ] Booking form lists available doctor shifts.
- [ ] Service worker intercepts fetch requests for daily schedules, storing them in IndexedDB.
- [ ] When network is offline, dashboard displays a read-only list from cache with an offline warning banner.

**Verification:**
- [ ] Playwright tests run with network emulation (offline) to ensure cached schedules are rendered: `npm run test:e2e`
- [ ] Offline banner displays: `"You are currently offline. Viewing cached schedule."`

**Dependencies:** Task 5, Task 11

**Files likely touched:**
- `frontend/src/pages/BookAppointment.tsx`
- `frontend/src/service-worker.ts`
- `frontend/src/services/sync.ts`
- `frontend/src/components/OfflineBanner.tsx`

**Estimated scope:** Medium: 3-5 files

---

#### Task 13: Clinical Records Database Schema & Encryption Layer
**Description:** Setup clinical records schema and integrate backend AES-256-GCM envelope encryption using AWS KMS to protect patient clinical fields.

**Acceptance criteria:**
- [ ] `clinical_records` table created with columns `encrypted_notes`, `encrypted_diagnosis`, `encrypted_prescriptions`, and `kms_key_version`.
- [ ] Cryptography service uses PyCryptodome (AES-256-GCM) with Data Encryption Keys (DEKs) wrapped by AWS KMS.
- [ ] Plaintext is never saved in logs, and a local mock KMS provider is configured for development/testing environments.

**Verification:**
- [ ] Unit tests verify encryption/decryption cycles: `pytest backend/tests/unit/test_cryptography.py`
- [ ] Database inspect checks that values in `encrypted_notes` are encrypted strings.

**Dependencies:** Task 10

**Files likely touched:**
- `backend/src/models/medical.py`
- `backend/src/core/kms.py`
- `backend/src/core/fields.py`
- `backend/tests/unit/test_cryptography.py`

**Estimated scope:** Medium: 3-5 files

---

#### Task 14: Clinical Consultation Endpoints & Audit Logging
**Description:** Build API endpoints for recording and reading clinical records, enforcing strict doctor-only access and logging reads/writes to immutable audit logs.

**Acceptance criteria:**
- [ ] Endpoints `POST /api/v1/clinical-records` and `GET /api/v1/clinical-records/{id}` enforce doctor-only scope.
- [ ] Access requests log a row in `security_audit_logs` containing IP, actor ID, and action description within the same DB transaction.
- [ ] System admins are blocked from clinical API routes (scopes lack decrypt authorization).

**Verification:**
- [ ] Access integration tests run: `pytest backend/tests/integration/test_clinical_access.py`
- [ ] Confirm table write: read attempt by administrator fails with HTTP 403.

**Dependencies:** Task 4, Task 13

**Files likely touched:**
- `backend/src/api/clinical.py`
- `backend/src/services/audit.py`
- `backend/tests/integration/test_clinical_access.py`

**Estimated scope:** Medium: 3-5 files

---

#### Task 15: Doctor Consultation Workspace UI
**Description:** Build a tablet-optimized React page for doctors to access patient medical histories, manage active consults, and write secure clinical notes.

**Acceptance criteria:**
- [ ] Doctor dashboard displays queue of scheduled appointments for the active doctor.
- [ ] Selecting a patient retrieves decrypted medical history.
- [ ] Consultation form allows inputting clinical notes, diagnoses, and prescriptions, encrypting payload on submit.

**Verification:**
- [ ] Frontend page tests render successfully: `npm run test -- --grep "DoctorDashboard"`
- [ ] Manual test: loading doctor dashboard retrieves patient history, and adding new records writes them to the DB as ciphertext.

**Dependencies:** Task 5, Task 14

**Files likely touched:**
- `frontend/src/pages/DoctorDashboard.tsx`

**Estimated scope:** Medium: 3-5 files

---

### Phase 3: Extended Features, Polish & Deployment Prep

#### Task 16: Cancellation Rules & Penalty Checks
**Description:** Implement late-cancellation constraints: warn users on late-cancellations (less than 2 hours before appointment), log penalty flags, and restrict self-service booking if violations exceed 4.

**Acceptance criteria:**
- [ ] Penalty tracker tracks late-cancellations per patient.
- [ ] Cancellation API raises warning alerts or restricts bookings if user has 4 active penalties.
- [ ] Receptionist override allows bypassing restrictions for emergencies.

**Verification:**
- [ ] Unit tests verify progressive penalties and restriction triggers: `pytest backend/tests/unit/test_penalties.py`
- [ ] Integration tests verify override permissions: `pytest backend/tests/integration/test_restrictions.py`

**Dependencies:** Task 11

**Files likely touched:**
- `backend/src/services/penalties.py`
- `backend/src/api/appointments.py`
- `frontend/src/components/CancellationModal.tsx`

**Estimated scope:** Medium: 3-5 files

---

#### Task 17: Front Desk Queue Board & Check-in UI
**Description:** Build receptionist arrival check-in flow and real-time active patient queue board.

**Acceptance criteria:**
- [ ] Receptionist check-in endpoint updates appointment status to "arrived".
- [ ] UI displays queue board of arrived patients, waiting, and completed states.
- [ ] Front-desk interface includes controls to override booking restriction blocks.

**Verification:**
- [ ] Unit tests check status transitions: `pytest backend/tests/unit/test_checkin.py`
- [ ] Manual check: checking in a patient immediately lists them as "Waiting" on the queue board.

**Dependencies:** Task 12, Task 16

**Files likely touched:**
- `backend/src/api/appointments.py`
- `frontend/src/pages/ReceptionistDashboard.tsx`

**Estimated scope:** Medium: 3-5 files

---

#### Task 18: Manager Dashboard & Report Generation
**Description:** Implement APIs and frontend charts for single-branch and consolidated cross-branch operation metrics.

**Acceptance criteria:**
- [ ] API endpoints retrieve appointment counts, check-in success rates, average wait times, and cancellation rates.
- [ ] Access to reports restricted to `manager`, `executive`, and `admin` roles.
- [ ] Frontend charts render metrics (using Chart.js, Recharts, or CSS grids).

**Verification:**
- [ ] Integration tests check report calculations: `pytest backend/tests/integration/test_reports.py`
- [ ] Executive user successfully views aggregated multi-branch graphs in UI.

**Dependencies:** Task 4, Task 17

**Files likely touched:**
- `backend/src/api/reports.py`
- `frontend/src/pages/ManagerDashboard.tsx`

**Estimated scope:** Medium: 3-5 files

---

#### Task 19: Security Scanning, Optimization & Polish
**Description:** Polish endpoints, add DB performance indexes, configure Swagger documentation, and perform static security scans.

**Acceptance criteria:**
- [ ] Core tables have indexes on foreign keys, `phone_number`, `email`, and appointment datetime columns.
- [ ] OpenAPI documentation is annotated with descriptive tags, query params, and status codes.
- [ ] Codebase passes Python Bandit and npm security audit checks.

**Verification:**
- [ ] Database queries trace index usage via `EXPLAIN ANALYZE`.
- [ ] Security scanners return zero critical issues: `bandit -r backend/src` and `npm audit --audit-level=high`.

**Dependencies:** All previous tasks

**Files likely touched:**
- `backend/src/main.py`
- `backend/alembic/versions/`
- `backend/pyproject.toml`

**Estimated scope:** Small: 1-2 files

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Database Lock Deadlocks** | High | Apply small, strict transaction timeouts (3.0s) and enforce ordered locking sequences (always lock doctor shifts before checking conflicting appointments). |
| **AWS KMS Downtime** | High | Implement a memory cache (DEK cache) to minimize KMS API calls. Provide fallback mocks for offline development/test modes. |
| **High SMS Failures in Nigeria** | Medium | Utilize Termii SMS as the primary fallback, which routes via configured domestic corporate channels to bypass Do-Not-Disturb (DND) restrictions. |
| **Service Worker Sync Failures** | Medium | Handle IndexedDB write conflicts using Dexie's transaction system, ensuring offline schedules fallback to local state if write fails. |

---

## Open Questions

1. **OTP Custom SMS Senders:** Do we need to register pre-approved SMS templates with Termii/Infobip under a custom clinic Sender ID, or can we utilize the default shared sender routes during MVP pilot?
2. **Offline Data Security:** Since patient schedules are saved in browser IndexedDB for offline access, do we need to encrypt the IndexedDB cache using a derived client-side key, or is default browser sandbox storage sufficient?
3. **AWS KMS Environment Setup:** Will the development KMS keys be provisioned dynamically using AWS Terraform scripts, or should the backend support a fallback local file-based key generator for developer testing?
