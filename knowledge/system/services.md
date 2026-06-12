# CMP — Services

**Source**: Technical Specification + C4 Architecture Models (2026-06-04)

---

## Backend Services (FastAPI Modules)

### Authentication & RBAC Service
- **Purpose**: Validates JWT tokens and enforces role-based access control.
- **Technology**: FastAPI Security Scopes, JWT (OAuth2 Bearer)
- **API surface**: `POST /api/v1/auth/login`, `POST /api/v1/auth/verify-request`, `POST /api/v1/auth/verify-code`
- **Dependencies**: `users` table, `verification_otps` table

### Scheduling Engine
- **Purpose**: Validates doctor availability, executes pessimistic DB locks, prevents double-bookings (FR-004, FR-019).
- **Technology**: SQLAlchemy async with `SELECT ... FOR UPDATE`
- **API surface**: `POST /api/v1/appointments`, `PATCH /api/v1/appointments/{id}`, `DELETE /api/v1/appointments/{id}`
- **Dependencies**: `doctor_availability`, `appointments` tables; PostgreSQL transaction locks

### Clinical Record Service
- **Purpose**: Column-level AES-256-GCM encryption/decryption for patient clinical records; KMS integration.
- **Technology**: Python `cryptography` library, AWS KMS SDK (boto3), envelope encryption with DEK caching
- **API surface**: `POST /api/v1/clinical-records`, `GET /api/v1/clinical-records/{patient_id}`
- **Dependencies**: `clinical_records` table, AWS KMS, `security_audit_logs` table

### OTP Verification Engine
- **Purpose**: Channel-agnostic OTP generation, delivery, and validation with rate limiting.
- **Technology**: Python, Redis (for rate limit counters), Celery (delivery tasks)
- **Business rules**: 10-min TTL, 5 attempts max, 1 active session per phone, 3 requests/15min rate limit
- **Dependencies**: `verification_otps` table, Notification Service

### Notification Service Abstraction
- **Purpose**: Strategy Pattern abstraction over WhatsApp, Termii SMS, and Infobip SMS providers with async failover.
- **Technology**: Python, Celery, Redis queue
- **Failover chain**: WhatsApp → Termii SMS → Infobip SMS
- **Dependencies**: Redis Task Queue, `NotificationLog` table, external gateway APIs

---

## Frontend Application (React PWA)

### Patient Portal
- **Purpose**: Patient self-registration, appointment booking, rescheduling/cancellation, lab results view.
- **Technology**: Vite + React, Workbox, Dexie.js/IndexedDB
- **Offline capability**: Read-only appointment cache via Service Worker + IndexedDB (≥2h)

### Staff Dashboard (Receptionist / Doctor)
- **Purpose**: Walk-in registration, check-in management, daily schedule view, clinical notes entry.
- **Technology**: Vite + React, Workbox, Dexie.js/IndexedDB
- **Offline capability**: Current-day appointment list cached locally (≥2h read-only)

### Management Dashboard
- **Purpose**: Real-time branch operational reports; cross-clinic aggregated metrics for senior management.
- **Technology**: Vite + React

---

## External Integrations

| Service | Protocol | Purpose | Direction |
|---|---|---|---|
| WhatsApp Business Cloud API | REST (HTTPS) | Primary transactional notification channel | Outbound |
| Termii API | REST (HTTPS) | Primary Nigerian SMS (DND-bypass) | Outbound |
| Infobip API | REST (HTTPS) | Secondary SMS failover | Outbound |
| AWS KMS | AWS SDK | Clinical record key management | Outbound |

---

## API Contracts (Key Endpoints)

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
- **Behaviour**: Notes encrypted via AES-256-GCM before DB write; audit log written in same transaction

### POST /api/v1/auth/verify-request
- **Access**: Public
- **Request**: `{ phone_number }`
- **Response 200**: `{ message: "We've sent a verification code to your phone" }`
- **Behaviour**: Enqueues OTP delivery task (WhatsApp-first, SMS fallback on 15s timeout)
