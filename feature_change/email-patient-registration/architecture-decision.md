# Architecture Decision

## Feature

Email-based Patient Registration with Auth Email & Separate Patient/Staff Login

## Evaluation Input

- **Change Impact Map**: `change-impact-map.md` (Domain: HIGH, Database: HIGH, API: HIGH, Security: HIGH)
- **Architecture SSOT Source**: `knowledge/architecture/`

## Governance Checks

### 1. Service Boundaries

- **Status**: FAILED
- **Details**: The current SSOT defines a single **Authentication & RBAC Service** (FastAPI Security Scopes) with a unified API surface (`POST /api/v1/register`, `POST /api/v1/verify-request`, `POST /api/v1/verify-code`, `POST /api/v1/login`, `GET /api/v1/me`). The C4 Level 3 components diagram shows a single Auth component with no decomposition. The proposed change fundamentally restructures this boundary by:
  - Splitting authentication into two distinct service boundaries: **Patient Authentication** and **Staff Authentication**, each with separate endpoints, separate databases, and separate auth flows.
  - Introducing a new **Email Verification Service** boundary (email generation, token management, password creation flow) that does not exist in the current architecture.
  - Potentially creating a separate **Patient Database** boundary, which would require a new container in the C4 Level 2 containers diagram and cross-database transaction coordination.
  - This represents a significant architectural decomposition that is not reflected in the current C4 or UML models. While the decomposition itself is architecturally sound, the new service boundaries must be formally defined, documented, and approved before implementation.

### 2. Ownership

- **Status**: PASSED
- **Details**: The SSOT does not define explicit team or component ownership rules beyond the agent definitions (architecture-agent.md, developer-agent.md, review-agent.md, testing-agent.md). The proposed change does not violate any existing ownership constraints. The natural decomposition creates two clear ownership domains:
  - **Patient Auth Domain**: Email registration, email verification tokens, password creation, patient login
  - **Staff Auth Domain**: Existing staff email+password login (unchanged)
  - These domains are distinct and can be clearly assigned. No cross-team ownership conflicts arise since the entire codebase is governed by a single development team.

### 3. Dependencies

- **Status**: FAILED
- **Details**: The proposed change introduces new dependencies and modifies existing dependency pathways:
  - **New external integration**: An email notification provider (e.g., SMTP, SendGrid, AWS SES) is required. This triggers the `new_provider_or_integration` sync rule in `knowledge/ssot.yaml` which mandates a new ADR and updates to `knowledge/architecture/C4/system-context.md`, `knowledge/system/services.md`, and `knowledge/architecture/ADR/`. The current external integrations (WhatsApp, Termii, Infobip, AWS KMS) are all covered by ADR-001 through ADR-004; this new provider is not.
  - **Separate database dependency**: If separate databases for patients vs staff are implemented, this introduces a new cross-database dependency pattern. The current architecture assumes a single PostgreSQL database (ADR-001). Cross-database queries (e.g., appointments linking patients and doctors) would require application-level joins or distributed transactions, which are not currently supported by the architecture.
  - **Email verification token dependency**: A new `email_verification_tokens` table creates a new data dependency that must be accessible from the auth service.
  - **Dependency direction is maintained**: All new dependencies follow the correct direction (API → Service → DB/External). No circular dependencies or illegal direct dependencies (e.g., UI → DB) are introduced.
  - **C4 Level 2 impact**: The container diagram must be updated to show the new email provider container and the potential separate patient database container.

### 4. Design Patterns

- **Status**: PASSED
- **Details**: The proposed changes align with established architectural design patterns in the SSOT:
  - **REST API pattern**: New endpoints (`POST /api/v1/auth/patient/register`, `POST /api/v1/auth/patient/verify-email`, `POST /api/v1/auth/patient/login`, `POST /api/v1/auth/patient/resend-verification`) follow the existing FastAPI APIRouter conventions.
  - **Strategy Pattern (ADR-004)**: Email notification delivery can be integrated into the existing pluggable NotificationService abstraction as a new provider adapter. This is consistent with ADR-004's design philosophy.
  - **Password hashing**: bcrypt hashing for patient passwords follows the existing pattern used for staff passwords.
  - **JWT authentication**: Patient tokens can follow the same JWT OAuth2 Bearer pattern, with audience/issuer differentiation claims for patient vs staff (consistent with existing JWT usage).
  - **Rate limiting**: Email verification request rate limiting (3 requests/15min) follows the existing OTP rate limiting pattern.
  - **Token security**: Email auth tokens with short TTL, single-use, and cryptographic randomness follow the same security principles as OTP tokens.
  - **Alembic migrations**: Schema changes follow the existing Alembic migration pattern.
  - **No design pattern violations** are introduced by the proposed change.

## Verdict

**ARCHITECTURE CHANGE REQUIRED**

## Remediation / Notes

The following actions are required before this feature can be approved:

### 1. New ADR Required (ADR-005)

- **Scope**: Email-based Patient Registration Architecture
- **Must cover**:
  - Database separation strategy: **Same database vs separate databases** decision. Recommendation from change-impact-map: consider logical separation (different tables, different auth flows, different JWT claims) within the same database to avoid massive cross-database complexity.
  - Email notification service integration: Provider selection (SMTP/SendGrid/AWS SES), integration pattern, and how it fits into the existing NotificationService Strategy Pattern.
  - Password policy for patients: Minimum strength requirements, validation rules.
  - Auth token strategy for email verification links: Token generation, TTL (recommended: 60 minutes), single-use enforcement.
  - JWT token differentiation: Audience/issuer claims for patient vs staff tokens.

### 2. SSOT Artifacts to Update

| Artifact | Action Required |
| --- | --- |
| `knowledge/architecture/C4/system-context.md` | Add email notification provider as a new external system |
| `knowledge/architecture/C4/containers.md` | Add email provider container; potentially add separate patient database container |
| `knowledge/architecture/C4/components.md` | Add PatientAuth component, EmailVerification component; update Auth component to reflect decomposition |
| `knowledge/system/services.md` | Add new endpoints and services; update Authentication service documentation |
| `knowledge/system/data-models.md` | Add `email_verification_tokens` table; add `is_email_verified` column to `users` table |
| `knowledge/architecture/UML/class-diagrams.md` | Add new entities (EmailVerificationToken, PatientAuth) |
| `knowledge/architecture/UML/component-diagrams.md` | Add new service components |
| `knowledge/architecture/UML/sequence-diagrams.md` | Add email registration flow, email verification flow, password creation flow |
| `knowledge/architecture/UML/state-diagrams.md` | Add email verification states, password creation states |
| `knowledge/architecture/UML/activity-diagrams.md` | Add email registration control flow |
| `knowledge/ssot.yaml` | Update `next_id` to ADR-005; update completed_tasks |

### 3. Implementation Recommendations (from Change Impact Map)

- **Phase 1**: New email-based registration alongside existing OTP system (backward compatible)
- **Phase 2**: Migrate existing patients to new system
- **Phase 3**: Deprecate OTP-based patient auth
- **Consider scope**: Separate databases is a massive architectural change. Consider logical separation within the same database as a simpler alternative.

### 4. Architecture Validation Rules Affected

- **Rule 1 (Change Governance)**: Triggered - new ADR required
- **Rule 2 (C4 Synchronization)**: Triggered - system-context, containers, and components must be updated
- **Rule 3 (Pessimistic Locking)**: Not affected - booking endpoints unchanged
- **Rule 4 (Data Isolation)**: Triggered - new email_verification_tokens table must respect data classification rules
- **Rule 5 (UML Synchronization)**: Triggered - multiple UML diagrams must be updated
