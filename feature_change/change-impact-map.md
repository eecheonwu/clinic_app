# Change Impact Map

feature:
Email-based Patient Registration with Auth Email & Separate Patient/Staff Login

impact:
domain: HIGH
database: HIGH
API: HIGH
security: HIGH

---

## Detailed Impact Analysis

### Feature Description

1. **Email-based Patient Registration**:
   - New patient registration form must include an email input field
   - After registration, an authentication email is sent to the patient's email address
   - The email contains a link to a password creation page
   - Password creation page requires "create password" and "confirm password" inputs
   - Password is stored in the users database (bcrypt-hashed)
   - An informational message is displayed to the user: "An authentication email has been sent to your email address"

2. **Separate Login for Patients vs Staff**:
   - Staff login and patient login must use separate authentication flows
   - Each points to a different database (separate user stores)
   - This separation aims to simplify and secure each authentication path

### Domain Impact (HIGH)

**Rationale**: The core registration and authentication domain model is being fundamentally restructured.

| Aspect | Current (Phone+OTP) | Proposed (Email+Password) |
| --- | --- | --- |
| Registration trigger | Phone number → OTP | Email → Auth link → Password creation |
| Patient verification | OTP (WhatsApp/SMS) | Email verification link |
| Patient credential | None (OTP-based) | Password (bcrypt) |
| Login mechanism | Single endpoint (staff email+password; patient OTP) | Two separate endpoints + separate databases |
| Auth flow | OTP request → OTP verify → tokens | Register → Auth email → Create password → Login with email+password |

**Affected domain concepts**:

- `User` entity: New authentication context for patients
- `PatientRegistration`: New flow with email verification and password setup
- `Authentication`: Split into two separate flows (patient vs staff)
- `EmailVerificationToken`: New entity (replaces/supplements OTP)
- `PatientProfile`: May need additional fields for email verification status

### Database Impact (HIGH)

**Rationale**: The proposal for "different databases" for patients vs staff represents a fundamental architectural change. Even a minimal interpretation requires new tables and schema changes.

**Scenario A — Separate Databases (as stated)**:

- Requires provisioning a second PostgreSQL database instance
- All patient-related tables (`users` with role=patient, `patient_profiles`, `verification_otps`) would need to be migrated to a new patient database
- Staff-related tables remain in the existing database
- Cross-database queries (e.g., appointments linking patients and doctors) become significantly more complex
- Application data layer needs to support multiple database connections and routing
- Transactional integrity across databases becomes challenging (e.g., booking an appointment involving both patient and staff data)

**Scenario B — Same Database, Separate Auth Tables**:

- New `patient_auth` table: `id`, `email`, `password_hash`, `email_verified`, `verification_token`, `token_expires_at`
- New `email_verification_tokens` table: `id`, `email`, `token_hash`, `attempts`, `is_used`, `expires_at`, `created_at`
- Existing `users` table: `email` column already exists, but may need `is_email_verified` flag
- Existing `verification_otps` table: Phone-based OTP may remain for backward compatibility or be deprecated

**Minimum schema changes required**:

- New table: `email_verification_tokens` (or similar)
- New column: `users.is_email_verified` (BOOLEAN, default FALSE)
- New column: `users.email` may need NOT NULL constraint for patients
- Index on `users.email` already exists (partial for non-null)

### API Impact (HIGH)

**Rationale**: Multiple new endpoints needed, existing endpoints modified or deprecated.

**New endpoints**:

- `POST /api/v1/auth/patient/register` — Patient registration with email + phone + profile
- `POST /api/v1/auth/patient/verify-email` — Verify email auth token and set password
- `POST /api/v1/auth/patient/login` — Patient login with email + password
- `POST /api/v1/auth/patient/resend-verification` — Resend auth email

**Modified endpoints**:

- `POST /api/v1/auth/register` — Current endpoint uses phone+OTP; may be deprecated or modified to accept email
- `POST /api/v1/auth/login` — Currently staff-only email+password; may become staff-only or deprecated
- `POST /api/v1/auth/verify-request` — OTP-based; may be deprecated for patients
- `POST /api/v1/auth/verify-code` — OTP-based; may be deprecated for patients

**New schemas needed**:

- `PatientRegisterWithEmailRequest`: includes `email`, `phone_number`, `full_name`, `date_of_birth`, `gender`, `emergency_contact`
- `PatientVerifyEmailRequest`: includes `token`, `password`, `confirm_password`
- `PatientLoginRequest`: includes `email`, `password`
- `EmailVerificationResponse`: includes `message`, `token_valid`, etc.

**Affected service layer**:

- `AuthService`: Major refactoring needed
- New `PatientAuthService` (or separate from `StaffAuthService`)
- `NotificationService`: New email notification capabilities

### Security Impact (HIGH)

**Rationale**: Email-based authentication introduces new security vectors and the separation of databases creates new security boundaries.

**Email-based auth risks**:

- **Phishing**: Auth emails can be spoofed; need DKIM/SPF/DMARC configured
- **Email compromise**: Patient email account compromise could lead to account takeover
- **Token leakage**: Verification links in email could be intercepted; need short TTLs
- **Password policies**: Need minimum strength requirements for patient passwords
- **Rate limiting**: Email verification requests need rate limiting (similar to OTP: 3 requests/15min)

**Separate database security**:

- **Authentication boundary**: Patient credentials stored separately from staff credentials
- **Access control**: Different database credentials for patient vs staff connections
- **Audit trail**: Need clear audit logging for which database was accessed
- **Backup/restore**: Different backup strategies for patient vs staff databases

**Password creation flow security**:

- Auth token must be cryptographically random (secrets.token_urlsafe)
- Token must have short TTL (e.g., 60 minutes)
- Single-use token (invalidated after password creation)
- Password must be bcrypt-hashed (already pattern in system)
- Confirm password validation must be server-side (not just client-side)

**Affected security artifacts**:

- `core/security.py`: May need separate token validation for patient auth
- `core/config.py`: New configs for email service, separate DB connections
- JWT token claims: May need audience/issuer differentiation for patient vs staff tokens

### Affected Artifacts Summary

| Category | Artifact | Impact Level | Action |
| --- | --- | --- | --- |
| **Domain** | Registration flow | HIGH | Redesign from phone+OTP to email+password creation |
| **Domain** | Authentication flow | HIGH | Split into separate patient and staff flows |
| **Domain** | Email verification | HIGH | New domain concept (email verification tokens) |
| **Database** | `users` table | MEDIUM | Add `is_email_verified` column; modify `email` constraints |
| **Database** | New `email_verification_tokens` table | HIGH | Create new table for email auth tokens |
| **Database** | Separate patient database | HIGH | New database instance, connection config, data migration |
| **Database** | `verification_otps` table | LOW | May be deprecated for patients; kept for backward compat |
| **API** | `POST /api/v1/auth/register` | HIGH | Modify to accept email; or deprecate in favor of new endpoint |
| **API** | New `POST /api/v1/auth/patient/register` | HIGH | New endpoint for email-based registration |
| **API** | New `POST /api/v1/auth/patient/verify-email` | HIGH | New endpoint for email verification + password creation |
| **API** | New `POST /api/v1/auth/patient/login` | HIGH | New endpoint for patient login |
| **API** | `POST /api/v1/auth/login` | MEDIUM | May become staff-only; or separate staff login endpoint |
| **API** | Auth schemas | HIGH | New schemas for email-based flows |
| **Security** | Email auth token | HIGH | New token generation, validation, expiry, single-use |
| **Security** | Password policy | MEDIUM | Enforce for patient passwords |
| **Security** | Email delivery security | HIGH | DKIM/SPF/DMARC; TLS for email sending |
| **Security** | JWT token differentiation | MEDIUM | Patient vs staff token claims |
| **Frontend** | Registration page | HIGH | Add email input; change flow to show "auth email sent" |
| **Frontend** | New password creation page | HIGH | New page: create password + confirm password |
| **Frontend** | Patient login page | HIGH | New separate login form for patients |
| **Frontend** | Staff login page | MEDIUM | May remain same or be modified |
| **Notification** | Email notification service | HIGH | New service/capability for sending auth emails |
| **Config** | Database connection settings | HIGH | New config for separate patient database |
| **Config** | Email service settings | HIGH | SMTP/email API configuration |
| **Testing** | Auth tests | HIGH | New test suites for email-based flows |
| **Testing** | Integration tests | HIGH | Updated integration tests for split auth |
| **SSOT** | `knowledge/system/data-models.md` | HIGH | Update for new tables and schema changes |
| **SSOT** | `knowledge/system/services.md` | HIGH | Update for new endpoints and services |
| **SSOT** | `knowledge/system/overview.md` | MEDIUM | Update for new architecture |
| **SSOT** | `knowledge/architecture/C4/` | HIGH | Update C4 diagrams for new auth flow |
| **SSOT** | `knowledge/ssot.yaml` | MEDIUM | Update sync rules for new changes |

### Recommendations

1. **Consider Scope**: Implementing truly separate databases for patients vs staff is a massive architectural change that touches every layer of the system. Consider whether logical separation (different tables, different auth flows, different JWT claims) within the same database might achieve the same goals with less complexity.

2. **Gradual Migration**: If separate databases are required, plan a gradual migration:
   - Phase 1: New email-based registration alongside existing OTP system
   - Phase 2: Migrate existing patients to new system
   - Phase 3: Deprecate OTP-based patient auth

3. **New ADR Required**: This change is significant enough to warrant a new Architecture Decision Record (ADR-005) covering:
   - Database separation strategy (same DB vs separate DBs)
   - Email notification service integration
   - Password policy for patients
   - Auth token strategy for email verification links

4. **Email Service**: The system currently has no email sending capability. This requires either:
   - Extending the NotificationService to support email delivery
   - Adding a new email notification provider
   - This is a new integration requiring SSOT update per sync rules (`new_provider_or_integration`)
