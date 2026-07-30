# Review Agent Context — Clinic Modernization Platform (CMP)

## Project Context
The Clinic Modernization Platform (CMP) is a secure, decoupled clinic management system built with Vite + React on the frontend and FastAPI on the backend, targeting a chain of three private healthcare clinics in Nigeria. It features a Progressive Web App (PWA) shell for offline schedule viewing (resilient up to 2 hours), concurrent doctor-slot booking protected by relational database pessimistic locking, application-level medical record column encryption (via AES-256-GCM and AWS KMS), and a multi-channel message delivery engine (WhatsApp-first with SMS fallback) for patient verification OTPs.

## Current Architecture
Decoupled React PWA (served via CloudFront CDN) communicating with FastAPI application server via HTTPS / TLS 1.3 through AWS API Gateway. High-concurrency doctor scheduling utilizes PostgreSQL 16+ (AWS RDS) with database-level pessimistic locking (`SELECT ... FOR UPDATE`). Clinical notes, diagnoses, and prescriptions are encrypted in the application layer via AES-256-GCM with master keys managed by AWS KMS (envelope encryption). Background notification queue uses Celery + Redis with a strategy-based WhatsApp Cloud API primary route and Termii/Infobip SMS fallback routing.

## Constraints
- **Timeline**: Phase 1 MVP deployed in 4 months.
- **Data Privacy**: NDPR compliance mandatory; patient profiles must be handled confidentially, medical records are restricted.
- **Network Resiliency**: Must support sub-3.0s load time over Nigerian 3G/4G. Browser must cache current-day appointments for ≥2h read-only offline access.
- **Clinical Separation**: System administrators and database administrators MUST NOT be able to read clinical records or consultation notes.
- **Pessimistic Locking**: Active database transaction timeout set to 3.0s max to prevent deadlocks.
- **OTP Sessions**: Rate limits: max 3 verification requests per phone per 15 minutes, 10-minute TTL, max 5 attempts per session, 1 active OTP per phone.

## Active Decisions
- **ADR-001**: PostgreSQL 16+ as the primary datastore for relational integrity, concurrency control (`with_for_update()`), and future pgvector/semantic search support.
- **ADR-002**: Vite + React PWA (SPA) for sub-3s Nigerian network load time, Workbox/Dexie.js offline cache, and low CDN hosting costs.
- **ADR-003**: Application-Level AES-256-GCM Column Encryption + AWS KMS envelope encryption to enforce NDPR compliance and restrict medical record decryption to authorized doctor roles only.
- **ADR-004**: Strategy-Pattern-based Notification Service Abstraction + Celery/Redis queue for async multi-channel failover (WhatsApp → Termii SMS → Infobip SMS).

## Validation Rules
1. **Consistency Checks**: Before approving code merges, check that `ssot.yaml` is updated with the last sync date and authority logs if schemas or APIs were modified.
2. **Role-Based Authorization**: Verify that clinical API endpoints strictly apply the `doctor` scope security dependency. Reject PRs exposing clinical endpoints to database administrators, receptionists, or general patients.
3. **Audit Log Transactions**: Audit trail inserts (`security_audit_logs`) must be executed within the exact same database transaction block as the corresponding record mutations.
4. **Sync Compliance**: Verify that any schema modifications are mapped across both the database model files and `knowledge/system/data-models.md` to prevent document-code divergence.
5. **UML Consistency**: Verify that any architectural or behavioral shifts (e.g., locking strategies, OTP delivery retry fallback paths, patient restriction transitions) are fully mapped to updated UML diagrams in `knowledge/architecture/UML/` before merging.
