# UML Sequence Diagrams

## 1. Doctor Shift Validation & Concurrent Booking (Pessimistic Locking)

Illustrates how the database pessimistic locking mechanism (**FR-019**, **NFR-001** of [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md)) handles two concurrent requests trying to book the exact same doctor time-slot.

```mermaid
sequenceDiagram
    autonumber
    actor PatientA as Patient A Client
    actor PatientB as Patient B Client
    participant API as FastAPI Backend
    participant DB as PostgreSQL DB

    Note over PatientA, DB: Concurrent booking requests for Dr. X at Monday 9:00 AM
    PatientA->>API: POST /api/v1/appointments (Dr. X, 9:00 AM)
    PatientB->>API: POST /api/v1/appointments (Dr. X, 9:00 AM)

    critical Transaction A starts
        API->>DB: BEGIN Transaction A
        API->>DB: SELECT DoctorAvailability with_for_update() (Dr. X, Monday 9 AM - 9:30 AM)
        activate DB
        Note over DB: Lock acquired for Transaction A on DoctorAvailability row
    and Transaction B starts
        API->>DB: BEGIN Transaction B
        API->>DB: SELECT DoctorAvailability with_for_update() (Dr. X, Monday 9 AM - 9:30 AM)
        Note over DB: Transaction B BLOCKED, waiting for Lock on DoctorAvailability row
    end

    API->>DB: SELECT Appointments with_for_update() (Dr. X, Monday 9:00 AM)
    DB-->>API: No conflicting appointments found
    API->>DB: INSERT INTO appointments (Dr. X, Patient A, booked)
    API->>DB: COMMIT Transaction A
    deactivate DB
    Note over DB: Lock released. Transaction A committed.

    activate DB
    Note over DB: Transaction B unblocks, lock acquired by Transaction B
    DB-->>API: Returns DoctorAvailability shift data
    API->>DB: SELECT Appointments with_for_update() (Dr. X, Monday 9:00 AM)
    DB-->>API: Conflict found (Appointment for Patient A exists)
    API->>DB: ROLLBACK Transaction B
    deactivate DB
    Note over DB: Lock released. Transaction B rolled back.
    API-->>PatientA: HTTP 201 Created (Appointment ID)
    API-->>PatientB: HTTP 409 Conflict ("Slot is no longer available")
```

---

## 2. Hierarchical Verification & OTP Delivery Flow (WhatsApp-First, SMS Fallback)

Visualizes the multi-gateway verification flow (**OQ-002**, **INT-004** of [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md)) attempting delivery via WhatsApp, falling back to local Termii SMS, and backing up to Infobip, as decided in [ADR-004](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/ADR/ADR-004-pluggable-notification-failover.md).

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Patient Browser
    participant API as FastAPI Backend
    participant DB as PostgreSQL DB
    participant MQ as Task Queue (Celery/Redis)
    participant WA as WhatsApp API
    participant Termii as Termii SMS API
    participant Infobip as Infobip SMS API

    Patient->>API: POST /api/v1/auth/verify-request (phone_number)
    API->>DB: UPDATE verification_otps SET is_used = TRUE (invalidate existing active OTPs)
    API->>DB: INSERT INTO verification_otps (phone_number, hashed_otp, expires_at, status=Pending)
    API->>MQ: Enqueue Notification Failover Task (delivery_id)
    API-->>Patient: HTTP 200 OK {"message": "Verification code sent"}

    Note over MQ, WA: Primary Routing: WhatsApp Cloud API
    MQ->>WA: POST /v1/messages (Send OTP Template)
    
    alt WhatsApp Success
        WA-->>MQ: HTTP 200 OK (Status: Acknowledged)
        MQ->>DB: UPDATE verification_otps SET delivery_channel='whatsapp'
    else WhatsApp Fails (Timeout 15s or API Error)
        Note over MQ, Termii: Fallback Routing: Termii SMS Gateway
        MQ->>Termii: POST /api/sms/send (Primary SMS)
        alt Termii Success
            Termii-->>MQ: HTTP 200 OK (Sent)
            MQ->>DB: UPDATE verification_otps SET delivery_channel='sms_termii'
        else Termii Fails (Gateway Error / Timeout)
            Note over MQ, Infobip: Secondary Fallback Routing: Infobip SMS Gateway
            MQ->>Infobip: POST /sms/2/text/advanced (Secondary SMS)
            alt Infobip Success
                Infobip-->>MQ: HTTP 200 OK (Sent)
                MQ->>DB: UPDATE verification_otps SET delivery_channel='sms_infobip'
            else Infobip Fails
                Infobip-->>MQ: Connection Error
                MQ->>DB: UPDATE verification_otps SET delivery_status='failed'
            end
        end
    end
```

---

## 3. Clinical Consultation Logging & Audited Record Access

Represents the cryptographic workflow (**FR-006**, **FR-007**, **NFR-006**, **NFR-007**, **NFR-008** of [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md)) for writing encrypted records and logging emergency overrides, governed by [ADR-003](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/ADR/ADR-003-application-level-column-encryption.md).

```mermaid
sequenceDiagram
    autonumber
    actor Doc as Doctor Client
    participant API as FastAPI Backend
    participant KMS as AWS KMS
    participant DB as PostgreSQL DB

    Note over Doc, DB: Clinical Record Writing Flow (FR-006, NFR-006)
    Doc->>API: POST /api/v1/clinical-records (appointment_id, notes, diagnosis)
    API->>API: Verify User Role is 'doctor' (RBAC Enforcement)
    API->>KMS: Request GenerateDataKey (kms_key_version)
    KMS-->>API: Plaintext DEK & Encrypted DEK
    API->>API: Encrypt notes & diagnosis with Plaintext DEK via AES-256-GCM
    API->>DB: BEGIN Transaction
    API->>DB: INSERT INTO clinical_records (encrypted_notes, encrypted_diagnosis, kms_key_version)
    API->>DB: INSERT INTO security_audit_logs (action_type='WRITE_CLINICAL_RECORD', doctor_id)
    API->>DB: COMMIT Transaction
    DB-->>API: Success
    API-->>Doc: HTTP 201 Created

    Note over Doc, DB: Emergency Cross-Branch Record Access Flow (FR-007, NFR-008)
    Doc->>API: GET /api/v1/clinical-records/patient/{id}
    API->>API: Verify User Role is 'doctor'
    API->>DB: SELECT encrypted_notes, kms_key_version FROM clinical_records WHERE patient_id = {id}
    DB-->>API: Return Encrypted Data & kms_key_version
    API->>KMS: Decrypt Encrypted DEK (kms_key_version)
    KMS-->>API: Plaintext DEK
    API->>API: Decrypt notes with Plaintext DEK
    API->>DB: BEGIN Transaction (Log access)
    API->>DB: INSERT INTO security_audit_logs (action_type='READ_CLINICAL_RECORD', details='Emergency Cross-Branch Access')
    API->>DB: COMMIT Transaction
    API-->>Doc: Return Plaintext Patient clinical history
```
