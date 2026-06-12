# CMP — Data Models

**Source**: Technical Specification (2026-06-04)

---

## Enums

```sql
CREATE TYPE user_role AS ENUM ('patient', 'receptionist', 'doctor', 'manager', 'admin', 'executive');
CREATE TYPE appointment_status AS ENUM ('booked', 'cancelled', 'completed', 'no-show');
CREATE TYPE payment_status AS ENUM ('pending', 'deposit_paid', 'fully_paid', 'waived', 'refunded');
```

---

## Tables

### `users` — Auth (Unencrypted)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | `gen_random_uuid()` |
| phone_number | VARCHAR(15) UNIQUE | Nigerian phone |
| email | VARCHAR(255) UNIQUE | |
| password_hash | VARCHAR(255) | bcrypt |
| role | user_role ENUM | RBAC role |
| created_at / updated_at | TIMESTAMPTZ | |

### `patient_profiles` — Confidential (NDPR)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users | CASCADE DELETE |
| full_name | VARCHAR(255) | |
| date_of_birth | DATE | |
| gender | VARCHAR(10) | |
| emergency_contact | VARCHAR(255) | |
| created_at | TIMESTAMPTZ | |

### `doctor_availability` — Internal (FR-018: Time-bound shifts)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| doctor_id | UUID FK → users | CASCADE DELETE |
| branch_id | VARCHAR(50) | Branch identifier |
| start_datetime | TIMESTAMPTZ | CHECK: start < end |
| end_datetime | TIMESTAMPTZ | |
| is_cancelled | BOOLEAN | Default FALSE |
| created_at | TIMESTAMPTZ | |

### `appointments` — Internal
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| doctor_id | UUID FK → users | RESTRICT DELETE |
| patient_id | UUID FK → users | RESTRICT DELETE |
| branch_id | VARCHAR(50) | |
| start_datetime | TIMESTAMPTZ | CHECK: start < end |
| end_datetime | TIMESTAMPTZ | |
| status | appointment_status | Default 'booked' |
| payment_state | payment_status | Default 'pending' — INT-005 Phase 2 placeholder |
| booking_source | VARCHAR(50) | 'patient' / 'receptionist' / 'admin_override' |
| created_at / updated_at | TIMESTAMPTZ | |

### `clinical_records` — **Restricted Medical (Encrypted)**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| appointment_id | UUID UNIQUE FK → appointments | RESTRICT DELETE |
| patient_id | UUID FK → users | RESTRICT DELETE |
| doctor_id | UUID FK → users | RESTRICT DELETE |
| encrypted_notes | TEXT | AES-256-GCM (ciphertext + IV + tag) |
| encrypted_diagnosis | TEXT | AES-256-GCM |
| encrypted_prescriptions | TEXT | AES-256-GCM |
| kms_key_version | VARCHAR(100) | Envelope encryption key version |
| created_at | TIMESTAMPTZ | |

> ⚠️ **CRITICAL**: `encrypted_notes`, `encrypted_diagnosis`, `encrypted_prescriptions` are stored as ciphertext. Decryption only occurs in application memory for authenticated `doctor` role users.

### `verification_otps` — Internal
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| phone_number | VARCHAR(15) | |
| hashed_otp | VARCHAR(255) | Hashed to prevent DB compromise |
| attempts | INTEGER | Default 0; max 5 |
| is_used | BOOLEAN | Default FALSE; single-use |
| expires_at | TIMESTAMPTZ | 10-minute TTL |
| delivery_channel | VARCHAR(20) | 'whatsapp' or 'sms' |
| created_at | TIMESTAMPTZ | |

### `security_audit_logs` — Internal (Immutable, NFR-007)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID | NOT NULL (no FK — immutable) |
| action_type | VARCHAR(100) | e.g., 'READ_CLINICAL_RECORD', 'OVERRIDE_BOOKING' |
| patient_id | UUID | NOT NULL |
| ip_address | VARCHAR(45) | IPv4 or IPv6 |
| timestamp | TIMESTAMPTZ | Default CURRENT_TIMESTAMP |
| action_details | TEXT | NOT NULL |

---

## Booking Concurrency Pattern (FR-019)

Pessimistic lock sequence (pseudo-code):
```python
async def create_booking(db, booking_data):
    async with db.begin():
        # 1. Lock doctor's shift rows
        shift = await db.execute(
            select(DoctorAvailability)
            .filter(doctor_id, time overlap, not cancelled)
            .with_for_update()  # Pessimistic lock
        )
        if not shift: raise HTTP 400 "Doctor unavailable"

        # 2. Lock conflicting appointment rows
        conflict = await db.execute(
            select(Appointments)
            .filter(doctor_id, status='booked', time overlap)
            .with_for_update()
        )
        if conflict: raise HTTP 409 "Slot no longer available"

        # 3. Insert new appointment
        db.add(Appointment(**booking_data))
```

---

## OTP Security Policies

| Policy | Value |
|---|---|
| OTP TTL | 10 minutes |
| Single-use | `is_used = TRUE` after validation |
| Rate limit | Max 3 verification requests per phone per 15 minutes |
| Max attempts | 5 per OTP; exceeding invalidates the session |
| Active sessions | 1 active OTP per phone number (new request invalidates prior) |
