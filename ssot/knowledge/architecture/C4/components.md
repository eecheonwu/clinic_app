# C4 Level 3 — Component Diagram (FastAPI Backend)

**Source**: C4 Architecture Models (2026-06-04)

---

## FastAPI Backend Components

| Component | Technology | Responsibility |
|---|---|---|
| API Route Controllers | FastAPI APIRouters | Parses URLs & incoming requests; dispatches to services |
| Authentication & RBAC Manager | FastAPI Security Scopes | Validates JWTs; enforces user role permissions |
| Scheduling Engine | Python / SQLAlchemy | Doctor shift & slot validator; executes pessimistic locks |
| Clinical Record Service | Python / AWS KMS SDK | Column-level AES-256-GCM encryptor/decryptor; handles KMS integration |
| OTP Verification Engine | Python | Channel-agnostic OTP logic; rate-limiting & code validation |
| Notification Service Abstraction | Python / Celery | Enqueues async alert dispatches; implements Strategy Pattern failover |
| Admin Service | FastAPI APIRouter | Branch/user/availability management; admin-only endpoints |

---

## Component Flow

```
Incoming REST API Request
        ↓
[API Route Controllers]
        ↓
[Auth & RBAC Manager] ←→ [API Route Controllers]
        ↓
┌──────────────────────────────────────────┐
│  [Scheduling Engine]                     │──→ [PostgreSQL] (pessimistic locks)
│  [Clinical Record Service]               │──→ [AWS KMS] + [PostgreSQL]
│  [OTP Verification Engine]               │──→ [PostgreSQL]
│  [Notification Publisher]                │──→ [Redis Queue]
│  [Admin Service]                         │──→ [PostgreSQL]
└──────────────────────────────────────────┘
```

---

## Component Diagram (Mermaid)

```mermaid
graph TB
    APIRequest["Incoming REST API Requests"]

    subgraph FastAPIContainer ["FastAPI Backend Modules"]
        Router["API Route Controllers\nFastAPI APIRouters\nParses URLs & requests"]
        Auth["Authentication & RBAC Manager\nFastAPI Security Scopes\nValidates JWTs & user permissions"]
        Scheduler["Scheduling Engine\nDoctor shift & slot validator\nExecutes pessimistic locks"]
        ClinicalService["Clinical Record Service\nColumn-level encryptor/decryptor\nHandles KMS integrations"]
        OTPService["OTP Verification Engine\nChannel-agnostic logic\nRate-limiting & code validation"]
        NotificationPublisher["Notification Service Abstraction\nEnqueues async alert dispatches"]
        AdminService["Admin Service\nBranch/user/availability management\nAdmin-only endpoints"]
    end

    APIRequest --> Router
    Router --> Auth
    Auth --> Router
    Router --> Scheduler
    Router --> ClinicalService
    Router --> OTPService
    Router --> NotificationPublisher
    Router --> AdminService

    Scheduler -->|Pessimistic transactions| PostgreSQL[("PostgreSQL DB")]
    ClinicalService -->|Envelope Encryption| AWSKMS["AWS KMS"]
    ClinicalService -->|Write encrypted records| PostgreSQL
    OTPService -->|Write OTP sessions| PostgreSQL
    NotificationPublisher -->|Push async tasks| RedisQueue["Redis Task Queue"]
    AdminService -->|Admin operations| PostgreSQL
```

---

# C4 Level 4 — Database ERD

## Entities

| Table | Classification | Key Fields |
|---|---|---|
| `users` | Auth (unencrypted) | id (PK), phone_number (UK), email (UK), password_hash, role |
| `patient_profiles` | Confidential (NDPR) | id (PK), user_id (FK), full_name, date_of_birth, gender |
| `doctor_availability` | Internal | id (PK), doctor_id (FK), branch_id, start_datetime, end_datetime, is_cancelled |
| `appointments` | Internal | id (PK), doctor_id (FK), patient_id (FK), branch_id, start/end_datetime, status, payment_state, booking_source |
| `clinical_records` | Restricted (Medical) — Encrypted | id (PK), appointment_id (FK), patient_id (FK), doctor_id (FK), encrypted_notes, encrypted_diagnosis, encrypted_prescriptions, kms_key_version |
| `verification_otps` | Internal | id (PK), phone_number, hashed_otp, attempts, is_used, expires_at, delivery_channel |
| `security_audit_logs` | Internal (Immutable) | id (PK), user_id, action_type, patient_id, ip_address, timestamp, action_details |
| `notifications_log` | Internal | id (PK), recipient, delivery_type, provider, template_name, status, error_code, sent_at, delivery_attempts |

## Key Relationships

- `users` 1 → 0..1 `patient_profiles`
- `users` 1 → 0..* `doctor_availability` (as doctor)
- `users` 1 → 0..* `appointments` (as doctor or patient)
- `appointments` 1 → 0..1 `clinical_records`
- `users` 1 → 0..* `clinical_records` (as author/subject)

## ERD (Mermaid)

```mermaid
erDiagram
    users {
        uuid id PK
        varchar phone_number UK
        varchar email UK
        varchar password_hash
        user_role role
        timestamp created_at
    }
    patient_profiles {
        uuid id PK
        uuid user_id FK
        varchar full_name
        date date_of_birth
        varchar gender
        varchar emergency_contact
    }
    doctor_availability {
        uuid id PK
        uuid doctor_id FK
        varchar branch_id
        timestamp start_datetime
        timestamp end_datetime
        boolean is_cancelled
    }
    appointments {
        uuid id PK
        uuid doctor_id FK
        uuid patient_id FK
        varchar branch_id
        timestamp start_datetime
        timestamp end_datetime
        appointment_status status
        payment_status payment_state
        varchar booking_source
    }
    clinical_records {
        uuid id PK
        uuid appointment_id FK
        uuid patient_id FK
        uuid doctor_id FK
        text encrypted_notes
        text encrypted_diagnosis
        text encrypted_prescriptions
        varchar kms_key_version
        timestamp created_at
    }
    verification_otps {
        uuid id PK
        varchar phone_number
        varchar hashed_otp
        integer attempts
        boolean is_used
        timestamp expires_at
        varchar delivery_channel
        timestamp created_at
    }
    security_audit_logs {
        uuid id PK
        uuid user_id
        varchar action_type
        uuid patient_id
        varchar ip_address
        timestamp timestamp
        text action_details
    }
    notifications_log {
        uuid id PK
        varchar recipient
        varchar delivery_type
        varchar provider
        varchar template_name
        varchar status
        varchar error_code
        timestamp sent_at
        integer delivery_attempts
    }

    users ||--o| patient_profiles : "has profile"
    users ||--o{ doctor_availability : "schedules shifts"
    users ||--o{ appointments : "books as doctor/patient"
    appointments ||--o| clinical_records : "records findings"
    users ||--o{ clinical_records : "author/subject of"
```