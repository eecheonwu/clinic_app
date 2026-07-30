# CMP — Services

**Source**: Technical Specification + C4 Architecture Models (2026-06-04)

---

## Backend Services (FastAPI Modules)

### Authentication & RBAC Service
- **Purpose**: Validates JWT tokens and enforces role-based access control.
- **Technology**: FastAPI Security Scopes, JWT (OAuth2 Bearer)
- **API surface**: `POST /api/v1/register`, `POST /api/v1/verify-request`, `POST /api/v1/verify-code`, `POST /api/v1/login`, `GET /api/v1/me`
- **Dependencies**: `users` table, `verification_otps` table, `patient_profiles` table

### Scheduling Engine
- **Purpose**: Validates doctor availability, executes pessimistic DB locks, prevents double-bookings (FR-004, FR-019).
- **Technology**: SQLAlchemy async with `SELECT ... FOR UPDATE`
- **API surface**: 
  - `POST /api/v1/appointments` - Book appointment with pessimistic locking
  - `GET /api/v1/appointments` - List appointments for current user
  - `GET /api/v1/appointments/available-slots` - Get available slots for a doctor
  - `PATCH /api/v1/appointments/{appointment_id}` - Reschedule with re-locking
  - `DELETE /api/v1/appointments/{appointment_id}` - Cancel with penalty logic
- **Dependencies**: `doctor_availability`, `appointments` tables; PostgreSQL transaction locks

### Clinical Record Service
- **Purpose**: Column-level AES-256-GCM encryption/decryption for patient clinical records; KMS integration.
- **Technology**: Python `cryptography` library, AWS KMS SDK (boto3), envelope encryption with DEK caching
- **API surface**: 
  - `POST /api/v1/clinical-records` - Create clinical record (encrypted)
  - `GET /api/v1/clinical-records/{record_id}` - Get single clinical record
  - `PATCH /api/v1/clinical-records/{record_id}` - Update clinical record (re-encrypted)
  - `GET /api/v1/clinical-records/by-patient/{patient_id}` - List patient records
  - `PATCH /api/v1/clinical-records/{record_id}/release-lab-results` - Release lab results to patient (FR-008)
- **Dependencies**: `clinical_records` table, AWS KMS, `security_audit_logs` table

### OTP Verification Engine
- **Purpose**: Channel-agnostic OTP generation, delivery, and validation with rate limiting.
- **Technology**: Python, Redis (for rate limit counters), Celery (delivery tasks)
- **Business rules**: 10-min TTL, 5 attempts max, 1 active session per phone, 3 requests/15min rate limit
- **Dependencies**: `verification_otps` table, Notification Service

### Report Service
- **Purpose**: Branch/organization aggregation endpoints for operational metrics and notification delivery statistics.
- **Technology**: FastAPI, SQLAlchemy async, PostgreSQL
- **API surface**:
  - `GET /api/v1/reports/branch/daily` - Daily ops metrics (manager)
  - `GET /api/v1/reports/organization/summary` - Cross-clinic aggregated metrics (executive)
  - `GET /api/v1/reports/notification-delivery` - Delivery success rates per provider (admin)
- **Dependencies**: `appointments` table, `notifications_log` table

### Notification Service Abstraction
- **Purpose**: Strategy Pattern abstraction over WhatsApp, Termii SMS, and Infobip SMS providers with async failover.
- **Technology**: Python, Celery, Redis queue
- **Failover chain**: WhatsApp → Termii SMS → Infobip SMS
- **Dependencies**: Redis Task Queue, `NotificationLog` table, external gateway APIs

### Admin Service
- **Purpose**: Branch management, user role assignment, and system configuration.
- **Technology**: FastAPI, SQLAlchemy async, PostgreSQL
- **API surface**:
  - `GET /api/v1/admin/branches` - List all branches
  - `GET /api/v1/admin/branches/{branch_id}` - Get single branch
  - `POST /api/v1/admin/branches` - Create branch
  - `PATCH /api/v1/admin/branches/{branch_id}` - Update branch
  - `DELETE /api/v1/admin/branches/{branch_id}` - Delete branch
  - `GET /api/v1/admin/users` - List users (filterable by role)
  - `GET /api/v1/admin/users/{user_id}` - Get single user
  - `PATCH /api/v1/admin/users/{user_id}/role` - Update user role
  - `GET /api/v1/admin/availability` - List availability slots
  - `POST /api/v1/admin/availability` - Create availability slot
  - `PATCH /api/v1/admin/availability/{id}` - Update availability slot
  - `DELETE /api/v1/admin/availability/{id}` - Delete availability slot
  - `GET /api/v1/admin/settings` - Get system settings
  - `PATCH /api/v1/admin/settings` - Update system settings
- **Dependencies**: `users` table, `doctor_availability` table, `branches` table (future)

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
- **Auto-refresh**: 30-second polling interval

### Admin Console
- **Purpose**: Branch CRUD operations, user role management, availability management.
- **Technology**: Vite + React
- **Features**: Tab-based interface for branches, users, availability, and settings

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

**Description**: Book an appointment with pessimistic locking

**Access**: `patient`, `receptionist`, `manager`

**Request Body**:
```json
{
  "doctor_id": "uuid-string",
  "branch_id": "branch_001",
  "start_datetime": "2026-07-09T10:00:00+01:00",
  "end_datetime": "2026-07-09T11:00:00+01:00"
}
```

**Responses**:
- 201: Appointment created successfully
- 401: Not authenticated
- 409: Time slot already booked (conflict)
- 500: Server error

---

### GET /api/v1/appointments

**Description**: List appointments for current user

**Access**: Authenticated (any role)

**Query Parameters**:
- `status`: Filter by appointment status (optional)

**Response 200**:
```json
{
  "appointments": [
    {
      "id": "uuid-string",
      "doctor_id": "uuid-string",
      "patient_id": "uuid-string",
      "branch_id": "branch_001",
      "start_datetime": "2026-07-09T10:00:00+01:00",
      "end_datetime": "2026-07-09T11:00:00+01:00",
      "status": "booked",
      "payment_state": "pending"
    }
  ]
}
```

---

### GET /api/v1/appointments/available-slots

**Description**: Get available time slots for a doctor

**Access**: Public (rate limited)

**Query Parameters**:
- `doctor_id`: Doctor's UUID (required)
- `date`: Date to check availability (required)

**Response 200**:
```json
{
  "slots": [
    {
      "start": "2026-07-09T10:00:00+01:00",
      "end": "2026-07-09T11:00:00+01:00",
      "is_available": true
    }
  ]
}
```

---

### PATCH /api/v1/appointments/{appointment_id}

**Description**: Reschedule an appointment with re-locking

**Access**: `patient`, `receptionist`, `manager`, `admin`

**Request Body**:
```json
{
  "start_datetime": "2026-07-10T10:00:00+01:00",
  "end_datetime": "2026-07-10T11:00:00+01:00"
}
```

**Responses**:
- 200: Appointment rescheduled
- 401: Not authenticated
- 403: Not authorized
- 404: Appointment not found
- 409: New time slot already booked

---

### DELETE /api/v1/appointments/{appointment_id}

**Description**: Cancel an appointment with tiered penalty logic

**Access**: `patient`, `receptionist`, `doctor`, `manager`, `admin`

**Responses**:
- 200: Appointment cancelled (with penalty message)
- 401: Not authenticated
- 403: Not authorized
- 404: Appointment not found
- 400: Already cancelled

**Penalty Tiers**:
- Tier 1: Cancellation < 2 hours before appointment (strict penalty)
- Tier 2: Cancellation >= 2 hours before appointment (warning)
- Tier 3: Staff override (admin/manager) - logs to audit

---

### POST /api/v1/clinical-records

- **Access**: `doctor` only
- **Request**: `{ appointment_id, patient_id, notes, diagnosis, prescriptions }`
- **Response 201**: `{ record_id, status: "encrypted_and_stored" }`
- **Behaviour**: Notes encrypted via AES-256-GCM before DB write; audit log written in same transaction (NFR-006, NFR-007)

---

### PATCH /api/v1/clinical-records/{record_id}/release-lab-results

**Description**: Release lab results to patient

**Access**: `doctor` only

**Request Body**:
```json
{
  "lab_results": "Lab test results text",
  "released": true
}
```

**Response 200**: Updated clinical record with decrypted fields

---

### POST /api/v1/auth/verify-request

- **Access**: Public
- **Request**: `{ phone_number }`
- **Response 200**: `{ message: "We've sent a verification code to your phone" }`
- **Behaviour**: Enqueues OTP delivery task (WhatsApp-first, SMS fallback on 15s timeout)

---

### POST /api/v1/register

- **Access**: Public
- **Request**: `{ phone_number, full_name, date_of_birth?, gender?, emergency_contact? }`
- **Response 201**: `{ user: { id, phone_number, role }, tokens: { access_token, refresh_token } }`
- **Behaviour**: Creates patient user with auto-generated password; returns JWT tokens for initial access

---

### POST /api/v1/login

- **Access**: Public (staff only)
- **Request**: `{ email, password }`
- **Response 200**: `{ access_token, refresh_token, token_type, expires_in }`
- **Behaviour**: Authenticates staff user (non-patient roles); returns JWT tokens

---

### GET /api/v1/me

- **Access**: Authenticated (any role)
- **Response 200**: `{ id, phone_number, email, role, is_verified }`
- **Behaviour**: Returns current authenticated user's information

---

### GET /api/v1/reports/branch/daily

**Description**: Get daily operational report for a branch

**Access**: `manager` only

**Query Parameters**:
- `branch_id`: Branch identifier (required)
- `report_date`: Date for the report (optional, defaults to today)

**Response 200**:
```json
{
  "branch_id": "branch_001",
  "report_date": "2026-07-09",
  "total_appointments": 18,
  "completed_appointments": 5,
  "cancelled_appointments": 2,
  "no_show_appointments": 1,
  "pending_appointments": 10,
  "utilization_rate": 55.5,
  "total_revenue": 0.0,
  "generated_at": "2026-07-09T18:00:00+01:00"
}
```

---

### GET /api/v1/reports/organization/summary

**Description**: Get organization-wide summary report

**Access**: `executive` only

**Query Parameters**:
- `start_date`: Start date of report period (required)
- `end_date`: End date of report period (required)

**Response 200**:
```json
{
  "start_date": "2026-06-09",
  "end_date": "2026-07-09",
  "total_appointments": 95,
  "completed_appointments": 60,
  "cancelled_appointments": 20,
  "no_show_appointments": 15,
  "overall_utilization_rate": 63.2,
  "branch_summaries": [
    {
      "branch_id": "branch_001",
      "total_appointments": 50,
      "completed_appointments": 30,
      "cancelled_appointments": 10,
      "no_show_appointments": 10,
      "utilization_rate": 60.0
    }
  ],
  "generated_at": "2026-07-09T18:00:00+01:00"
}
```

---

### GET /api/v1/reports/notification-delivery

**Description**: Get notification delivery statistics

**Access**: `admin` only

**Query Parameters**:
- `start_date`: Start date of report period (required)
- `end_date`: End date of report period (required)

**Response 200**:
```json
{
  "start_date": "2026-06-09",
  "end_date": "2026-07-09",
  "total_notifications": 100,
  "successful_deliveries": 90,
  "failed_deliveries": 10,
  "success_rate": 90.0,
  "provider_stats": {
    "whatsapp": {"total": 55, "sent": 50, "failed": 5, "success_rate": 90.9},
    "termii": {"total": 45, "sent": 35, "failed": 10, "success_rate": 77.8}
  },
  "generated_at": "2026-07-09T18:00:00+01:00"
}
```

---

### Admin Endpoints

**GET /api/v1/admin/branches**
- **Access**: `admin` only
- **Response 200**: List of all branches

**POST /api/v1/admin/branches**
- **Access**: `admin` only
- **Request**: `{ name, address, phone, email }`
- **Response 201**: Created branch

**PATCH /api/v1/admin/users/{user_id}/role**
- **Access**: `admin` only
- **Request**: `{ role }`
- **Response 200**: Updated user

**GET /api/v1/admin/availability**
- **Access**: `admin`, `manager`
- **Query Parameters**: `doctor_id`, `branch_id`, `date`
- **Response 200**: List of availability slots