# Codebase Inventory

**Discovered**: 2026-07-30  
**Method**: SSOT Synchronization Audit (v2.1)

---

## Project Overview

**Name**: Clinic Modernization Platform (CMP)  
**Type**: Full-stack web application (FastAPI + React PWA)  
**Repository**: `https://github.com/eecheonwu/Project.git`  
**Latest Commit**: `969b7aaafe8b7bc3488c9388692e38daa138f4ea`

---

## Backend Structure (`src/backend/`)

### Entry Point

- `main.py` — FastAPI application entry point

### Core Configuration

- `core/config.py` — Pydantic Settings configuration
- `core/security.py` — JWT, password hashing, RBAC RoleChecker
- `db/session.py` — SQLAlchemy database session management

### Models (`models/`)

| File | Entity | Description |
| ------ | -------- | ------------- |
| `base.py` | Base | SQLAlchemy declarative base |
| `user.py` | User, PatientProfile | User accounts with roles, patient profiles |
| `appointment.py` | DoctorAvailability, Appointment | Scheduling with pessimistic locking |
| `clinical_record.py` | ClinicalRecord | Encrypted clinical data |
| `notification.py` | NotificationLog, VerificationOTP | OTP and notification tracking |
| `audit.py` | SecurityAuditLog | Immutable audit trail |

### Services (`services/`)

| File | Service | Description |
| ------ | --------- | ------------- |
| `auth_service.py` | AuthService | Registration, OTP, login, JWT |
| `scheduling_engine.py` | SchedulingEngine | Doctor availability, appointment booking |
| `clinical_record_service.py` | ClinicalRecordService | Encrypted clinical records with KMS |
| `notification_service.py` | NotificationService | Pluggable notification (WhatsApp/Termii/Infobip) |
| `report_service.py` | ReportService | Branch and organization reports |

### API Routes (`api/v1/`)

| Route | Files | Endpoints |
| ------- | ------- | ----------- |
| `/auth` | `router.py`, `schemas.py` | Register, verify-request, verify-code, login, me |
| `/appointments` | `router.py`, `schemas.py` | Availability, booking, reschedule, cancel |
| `/clinical-records` | `router.py`, `schemas.py` | Create, read clinical records |
| `/reports` | `router.py`, `schemas.py` | Branch, organization, notification reports |
| `/admin` | `router.py`, `schemas.py` | Branch management, user management |

### Workers (`workers/`)

- `celery_app.py` — Celery application configuration
- `tasks.py` — Async tasks (send_otp, send_notification)

### Utilities (`utils/`)

- `encryption.py` — AES-256-GCM encryption/decryption with KMS

### Database Migrations (`alembic/versions/`)

| Migration | Description |
| ----------- | ------------- |
| 0001 | Initial schema (users, branches) |
| 0002 | OTP verification |
| 0003 | Notifications log |
| 0004 | Doctor availability, appointments |
| 0005 | Clinical records |
| 0006 | Security audit logs |

### Other Backend Files

- `seed.py` — Database seed data (branch, admin, doctor, patient)
- `requirements.txt` — Python dependencies
- `Dockerfile` — Backend container
- `.env.example` — Environment variable template

---

## Frontend Structure (`src/frontend/`)

### Entry Point

- `src/main.tsx` — React application entry
- `src/App.tsx` — Root component with routing

### Pages (`src/pages/`)

| Directory | Page | Description |
| ----------- | ------ | ------------- |
| `auth/` | `LoginPage.tsx` | Staff login |
| `auth/` | `RegisterPage.tsx` | Patient registration (phone+OTP) |
| `auth/` | `VerifyOTPPage.tsx` | OTP verification |
| `Patient/` | `PatientDashboardPage.tsx` | Patient dashboard |
| `Appointments/` | `BranchSelectionPage.tsx` | Booking: branch selection |
| `Appointments/` | `DoctorSelectionPage.tsx` | Booking: doctor selection |
| `Appointments/` | `SlotSelectionPage.tsx` | Booking: time slot selection |
| `Appointments/` | `BookingConfirmationPage.tsx` | Booking: confirmation |
| `Appointments/` | `AppointmentListPage.tsx` | Appointment list view |
| `Appointments/` | `ReschedulePage.tsx` | Appointment reschedule |
| `Staff/` | `ReceptionistDashboardPage.tsx` | Receptionist dashboard |
| `Doctor/` | `DoctorDashboardPage.tsx` | Doctor clinical portal |
| `Manager/` | `ManagerDashboardPage.tsx` | Management dashboard |
| `Admin/` | `AdminDashboardPage.tsx` | Admin console |

### Components (`src/components/`)

- `Navigation.tsx` — Navigation bar
- `OfflineBanner.tsx` — Offline mode indicator

### Contexts (`src/contexts/`)

- `AuthContext.tsx` — Authentication state management

### Services (`src/services/`)

- `api.ts` — Axios instance with JWT interceptor
- `admin.ts` — Admin API calls
- `appointment.ts` — Appointment API calls
- `clinical.ts` — Clinical record API calls
- `report.ts` — Report API calls
- `db.ts` — Dexie.js IndexedDB for offline cache

### Types (`src/types/`)

- `admin.ts`, `appointment.ts`, `clinical.ts`, `report.ts` — TypeScript interfaces

### Utils (`src/utils/`)

- `storage.ts` — Local storage utilities

### Configuration

- `vite.config.ts` — Vite build configuration
- `tailwind.config.js` — Tailwind CSS
- `tsconfig.json` — TypeScript configuration
- `package.json` — Node dependencies
- `Dockerfile` — Frontend dev container
- `Dockerfile.prod` — Frontend production container (nginx)
- `nginx.conf` — Nginx configuration for production

---

## Test Structure (`tests/`)

### Backend Tests

| File | Tests | Description |
| ------ | ------- | ------------- |
| `test_main.py` | ~20 | Basic API health checks |
| `test_auth.py` | ~30 | Authentication and RBAC |
| `test_appointments.py` | ~25 | Appointment booking and scheduling |
| `test_clinical_records.py` | ~15 | Clinical record encryption |
| `test_concurrency.py` | ~10 | Pessimistic locking race conditions |
| `test_notification.py` | ~15 | Notification service and failover |
| `test_reports.py` | ~10 | Report endpoints |
| `test_router_integration.py` | 44 | Router integration tests |
| `test_otp_delivery.py` | 13 | OTP delivery system |
| `test_otp_delivery_fix.py` | 5 | OTP delivery fixes |
| `test_docker_setup.py` | ~5 | Docker setup validation |
| `test_setup.py` | ~5 | Test setup validation |

### Integration Tests (`tests/integration/`)

- Integration tests for booking flow and clinical encryption

### Load Tests (`tests/load/`)

- Performance and load tests

### Frontend Tests (`src/frontend/tests/`)

- `e2e/` — Playwright E2E tests (18 tests: 12 patient journey, 6 offline mode)

---

## Infrastructure Files

### Docker

- `docker-compose.yml` — Local development (db, redis, backend, worker, frontend, localstack)
- `docker-compose.prod.yml` — Production configuration
- `.env.docker` — Docker environment variables
- `.dockerignore` — Build exclusions
- `DOCKER-README.md` — Setup guide

### LocalStack

- `localstack-setup/init-kms.sh` — KMS key initialization for local dev

### Database

- `alembic.ini` — Alembic configuration
- `init-db/init.sql` — Initial database setup

### Build Scripts

- `Makefile` — Make targets
- `start-dev.bat` — Windows start script
- `start-dev.sh` — Linux/Mac start script

---

## Knowledge Base (`knowledge/`)

| Directory | Files | Status |
| ----------- | ------- | -------- |
| `agents/` | 4 agent definitions | ✅ Complete |
| `architecture/` | ADRs, C4, UML, evaluation | ✅ Complete |
| `deployment/` | deployment-guide.md | ✅ Created (sync v2.1) |
| `discovered/` | codebase-inventory.md | ✅ Created (sync v2.1) |
| `engineering/` | implementation-plan, task-plan | ✅ Synced |
| `product/` | requirements.md | ✅ Complete |
| `security/` | security-overview.md | ✅ Created (sync v2.1) |
| `system/` | overview, services, data-models | ✅ Complete |
| `testing/` | test-strategy, coverage, quality-status | ✅ Synced |
| `ssot.yaml` | SSOT configuration | ✅ Synced (v2.1) |

---

## Root-Level Analysis Artifacts

| File | Purpose |
| ------ | --------- |
| `change-impact-map.md` | Impact analysis for Email-based Patient Registration feature |
| `architecture-decision.md` | Architecture governance decision (ARCHITECTURE CHANGE REQUIRED) |
| `implementation-plan.md` | Root-level copy of implementation plan |

---

## Missing/Not Yet Created

| Item | Expected | Status |
| ------ | ---------- | -------- |
| `infra/` directory | Terraform IaC files | ❌ Not created (Task 5.1 pending) |
| `.github/workflows/` | CI/CD pipelines | ❌ Not created (Task 5.2 pending) |
| `knowledge/architecture/ADR/ADR-005-*` | Email registration ADR | ❌ Not created (pending feature) |
| Patient auth routes (`api/v1/auth/patient/`) | Email registration endpoints | ❌ Not created (pending feature) |
| Patient frontend pages (`PatientRegisterPage`, `PatientCreatePasswordPage`, `PatientLoginPage`) | Email registration UI | ❌ Not created (pending feature) |

---

## Technology Stack Summary

| Layer | Technology | Version |
| ------- | ----------- | --------- |
| Backend | Python + FastAPI | 3.11 / latest |
| Database | PostgreSQL | 15 |
| Cache | Redis | 7 |
| Task Queue | Celery | latest |
| Frontend | React + TypeScript + Vite | 18 / 5.x |
| CSS | Tailwind CSS | 3.x |
| PWA | Workbox + Dexie.js | latest |
| Encryption | AES-256-GCM + AWS KMS | — |
| Container | Docker + Docker Compose | — |
| Testing | pytest + Playwright | — |
| Migrations | Alembic | — |
