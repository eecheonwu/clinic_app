# Security Overview

**Last Updated**: 2026-07-30  
**Status**: Active

---

## Security Architecture Summary

The Clinic Modernization Platform (CMP) implements defense-in-depth security across multiple layers: data encryption, authentication, authorization, rate limiting, and audit logging.

---

## 1. Data Encryption (ADR-003)

### Column-Level Encryption

- **Algorithm**: AES-256-GCM (Galois/Counter Mode)
- **Implementation**: Application-level encryption in `ClinicalRecordService`
- **Key Management**: AWS KMS envelope encryption
- **Encrypted Fields**:
  - `clinical_records.encrypted_notes`
  - `clinical_records.encrypted_diagnosis`
  - `clinical_records.encrypted_prescriptions`
- **Key Versioning**: `kms_key_version` column tracks which KMS key version was used
- **Decryption**: Only in application memory for authenticated `doctor` role users
- **Plaintext Storage**: NEVER — ciphertext only at rest

### KMS Integration

- **Production**: AWS KMS managed key
- **Local Development**: LocalStack KMS emulation (`localstack-setup/init-kms.sh`)
- **Error Handling**: HTTP 503 on KMS unavailability; clinical data never written in plaintext

---

## 2. Authentication & Authorization

### Authentication Mechanism

- **Staff**: Email + password (bcrypt-hashed)
- **Patients (Current)**: Phone + OTP (WhatsApp/SMS via ADR-004 failover)
- **Patients (Future)**: Email + password (ADR-005 pending)
- **JWT**: OAuth2 Bearer token with expiration

### RBAC (Role-Based Access Control)

| Role | Access Scope |
| ------ | ------------- |
| `admin` | System administration, user management, branch management |
| `manager` | Branch/cross-branch reports, doctor availability management |
| `doctor` | Clinical records (read/write), patient history, lab results |
| `receptionist` | Appointment booking, check-in, walk-in registration, patient search |
| `patient` | Self-service booking, own appointments, own lab results |

### Critical RBAC Rule

- **System admins CANNOT read clinical records** (NFR-008) — enforced via `RoleChecker` dependency

### JWT Implementation

- **Signing**: HS256 with secret key from configuration
- **Expiration**: Configurable TTL
- **Claims**: User ID, role, scopes
- **Future (ADR-005)**: Audience claims (`aud: "patient"` vs `aud: "staff"`) for route separation

---

## 3. Rate Limiting

### OTP Rate Limiting

- **Limit**: 3 verification requests per phone number per 15 minutes
- **OTP TTL**: 10 minutes
- **Max Attempts**: 5 per OTP
- **Single Use**: `is_used=TRUE` after validation
- **Invalidation**: New OTP request invalidates prior active OTPs
- **HTTP Response**: 429 Too Many Requests on limit exceeded

### Future Rate Limiting (ADR-005)

- Email verification: 3 requests per email per 15 minutes (shared with registration)

---

## 4. Audit Logging

### Security Audit Logs Table

| Column | Purpose |
| -------- | --------- |
| `id` | UUID primary key |
| `user_id` | Acting user (NO FK for immutability) |
| `action_type` | `READ_CLINICAL_RECORD`, `WRITE_CLINICAL_RECORD`, `OVERRIDE_BOOKING`, etc. |
| `patient_id` | Affected patient |
| `ip_address` | Request origin IP |
| `timestamp` | Action timestamp |
| `action_details` | Additional context |

### Audit Log Triggers

- Clinical record access (read/write)
- Booking overrides (Tier 3 restriction override per FR-015)
- Cross-branch emergency access (FR-007)
- Failed authentication attempts

---

## 5. Notification Security (ADR-004)

### Provider Failover

- **Primary**: WhatsApp Business Cloud API
- **Secondary**: Termii SMS
- **Tertiary**: Infobip SMS
- **Failover Logic**: Automatic based on delivery failure
- **Logging**: All attempts logged in `notifications_log` table

### OTP Security

- Cryptographically random generation
- Short TTL (10 minutes)
- Single-use enforcement
- Rate limiting (3/15min)
- Max 5 attempts per OTP

---

## 6. Database Security

### Connection Security

- PostgreSQL with dedicated application user
- Connection pooling via SQLAlchemy
- Parameterized queries (SQL injection prevention)

### Data Isolation

- Branch-level data isolation for multi-branch clinics
- Patient data accessible only to assigned doctors and self
- Clinical records restricted to `doctor` role only

---

## 7. API Security

### Input Validation

- Pydantic schema validation on all endpoints
- SQL injection prevention via SQLAlchemy ORM
- Request size limits

### CORS

- Configurable allowed origins
- Credentials support for authenticated requests

### HTTPS

- Enforced in production via API Gateway/CloudFront
- TLS 1.2+ minimum

---

## 8. Frontend Security

### Token Storage

- JWT stored in localStorage (consider HttpOnly cookies for future)
- Token refresh on 401 responses
- Automatic logout on token expiry

### Route Guards

- Role-based route protection
- Redirect unauthenticated users to login
- Block access to unauthorized routes

---

## 9. Security NFRs Mapping

| NFR | Description | Implementation |
| ----- | ------------- | ---------------- |
| NFR-005 | System available 99.5% during clinic hours | Docker health checks, planned CloudWatch monitoring |
| NFR-006 | Clinical data encrypted at rest (AES-256) | ADR-003, AES-256-GCM, KMS envelope encryption |
| NFR-007 | Cross-branch emergency access with audit | Audit logging, explicit confirmation flow |
| NFR-008 | System admins cannot read clinical records | RBAC RoleChecker, doctor-only access |

---

## 10. Future Security Considerations (ADR-005)

When Email-based Patient Registration is implemented:

- **Password Policy**: Min 8 chars, uppercase, lowercase, digit, special character
- **Email Verification Tokens**: `secrets.token_urlsafe(32)`, bcrypt-hashed, 60-min TTL, single-use
- **JWT Audience Claims**: `aud: "patient"` vs `aud: "staff"` for route separation
- **Email Delivery Security**: DKIM/SPF/DMARC configuration, TLS for email transport
- **Phishing Prevention**: Short token TTLs, single-use tokens, rate limiting

---

## References

- `knowledge/architecture/ADR/ADR-003-application-level-column-encryption.md`
- `knowledge/architecture/ADR/ADR-004-pluggable-notification-failover.md`
- `knowledge/product/requirements.md` — NFR-005 through NFR-008
- `knowledge/system/data-models.md` — `security_audit_logs` table
- `knowledge/system/services.md` — Authentication & RBAC service
