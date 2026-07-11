# Architecture Agent Context — Clinic Modernization Platform (CMP)

## Project Context
The Clinic Modernization Platform (CMP) is a secure, decoupled clinic management system built with Vite + React on the frontend and FastAPI on the backend, targeting a chain of three private healthcare clinics in Nigeria. It features a Progressive Web App (PWA) shell for offline schedule viewing (resilient up to 2 hours), concurrent doctor-slot booking protected by relational database pessimistic locking, application-level medical record column encryption (via AES-256-GCM and AWS KMS), and a multi-channel message delivery engine (WhatsApp-first with SMS fallback) for patient verification OTPs.

## Current Architecture
Decoupled React PWA (served via CloudFront CDN) communicating with FastAPI application server via HTTPS / TLS 1.3 through AWS API Gateway. High-concurrency doctor scheduling utilizes PostgreSQL 16+ (AWS RDS) with database-level pessimistic locking (`SELECT ... FOR UPDATE`). Clinical notes, diagnoses, and prescriptions are encrypted in the application layer via AES-256-GCM with master keys managed by AWS KMS (envelope encryption). Background notification queue uses Celery + Redis with a strategy-based WhatsApp Cloud API primary route and Termii/Infobip SMS fallback routing.

Key logical relationships, database entities, component boundaries, runtime execution behaviors, state lifecycles, and control flows are formally defined in the UML Design Models:
- Static entities and relationships are modeled in [Class Diagrams](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/UML/class-diagrams.md).
- Logical boundaries and external endpoints within FastAPI are mapped in [Component Diagrams](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/UML/component-diagrams.md).
- Pessimistic locking concurrency, WhatsApp-first OTP fallback logic, and encrypted clinical write/override behaviors are captured in [Sequence Diagrams](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/UML/sequence-diagrams.md).
- The scheduling/payment states and patient booking restriction levels are mapped in [State Diagrams](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/UML/state-diagrams.md).
- Control flows for booking validation logic and cancellation penalty calculations are mapped in [Activity Diagrams](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/UML/activity-diagrams.md).

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
1. **Change Governance**: Any architectural change (e.g., adding an external integration, modifying the primary database) requires drafting a new Architecture Decision Record (ADR) under `knowledge/architecture/ADR/` following the existing format.
2. **C4 Synchronization**: Any changes to system boundaries, container integrations, or backend module relationships must immediately update `system-context.md`, `containers.md`, and `components.md` in `knowledge/architecture/C4/`.
3. **Pessimistic Locking**: New booking endpoints must follow the sequential row-level locking pattern (lock doctor shifts before checking/locking conflicting appointments).
4. **Data Isolation**: Verify that new data stores or tables respect the confidentiality (NDPR) and restricted medical classification rules, ensuring plaintexts are never visible to admins or database logs.
5. **UML Synchronization**: Any change to structural domain entities, backend logical services, scheduling workflows, verification paths, consultation routines, or scheduling lifecycle states must update the corresponding UML diagrams in `knowledge/architecture/UML/` (class, component, sequence, state, or activity diagrams) in sync with changes to code or requirements.
