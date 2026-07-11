# UML Class Diagrams

## Static Entity Domain Model

This diagram represents the database schema and system entities specified in the [Data Models](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/system/data-models.md) and [Product Requirements](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/product/requirements.md) (specifically **DR-004**).

```mermaid
classDiagram
    direction TB
    class UserRole {
        <<enumeration>>
        PATIENT
        RECEPTIONIST
        DOCTOR
        MANAGER
        ADMIN
        EXECUTIVE
    }

    class AppointmentStatus {
        <<enumeration>>
        BOOKED
        CANCELLED
        COMPLETED
        NO_SHOW
    }

    class PaymentStatus {
        <<enumeration>>
        PENDING
        DEPOSIT_PAID
        FULLY_PAID
        WAIVED
        REFUNDED
    }

    class User {
        +UUID id
        +String phone_number
        +String email
        +String password_hash
        +UserRole role
        +DateTime created_at
        +DateTime updated_at
    }

    class PatientProfile {
        +UUID id
        +UUID user_id
        +String full_name
        +Date date_of_birth
        +String gender
        +String emergency_contact
        +DateTime created_at
    }

    class DoctorAvailability {
        +UUID id
        +UUID doctor_id
        +String branch_id
        +DateTime start_datetime
        +DateTime end_datetime
        +Boolean is_cancelled
        +DateTime created_at
        +check_dates()
    }

    class Appointment {
        +UUID id
        +UUID doctor_id
        +UUID patient_id
        +String branch_id
        +DateTime start_datetime
        +DateTime end_datetime
        +AppointmentStatus status
        +PaymentStatus payment_state
        +String booking_source
        +DateTime created_at
        +DateTime updated_at
        +check_app_dates()
    }

    class ClinicalRecord {
        +UUID id
        +UUID appointment_id
        +UUID patient_id
        +UUID doctor_id
        +String encrypted_notes
        +String encrypted_diagnosis
        +String encrypted_prescriptions
        +String kms_key_version
        +DateTime created_at
    }

    class VerificationOTP {
        +UUID id
        +String phone_number
        +String hashed_otp
        +Integer attempts
        +Boolean is_used
        +DateTime expires_at
        +String delivery_channel
        +DateTime created_at
    }

    class SecurityAuditLog {
        +UUID id
        +UUID user_id
        +String action_type
        +UUID patient_id
        +String ip_address
        +DateTime timestamp
        +String action_details
    }

    UserRole <-- User : role type
    AppointmentStatus <-- Appointment : status type
    PaymentStatus <-- Appointment : payment_state type

    User "1" -- "0..1" PatientProfile : owns
    User "1" -- "*" DoctorAvailability : schedules shifts
    User "1" -- "*" Appointment : books as doctor or patient
    Appointment "1" -- "0..1" ClinicalRecord : references
    User "1" -- "*" ClinicalRecord : authors/subject of
```
