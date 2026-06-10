# Implementation Plan: Core Architecture Setup

**Branch**: `001-core-architecture` | **Date**: 2026-06-10 | **Spec**: [specs/001-core-architecture/spec.md](file:///C:/Users/DELL/Documents/Project/clinic_app_ase/clinic_app/specs/001-core-architecture/spec.md)

## Summary
Setup the foundational decoupled architecture for the Clinic Modernization Platform (CMP), including an asynchronous FastAPI backend, a PostgreSQL relational database with row-level pessimistic locking, a Vite + React PWA frontend with local IndexedDB cache, application-level column encryption for patient records, a strategy-based notification failover gateway, and a comprehensive mandatory testing framework.

## Technical Context

**Language/Version**: Python 3.12+ (Backend) | TypeScript/JavaScript (Frontend)

**Primary Dependencies**:
* Backend: FastAPI, SQLAlchemy / SQLModel, Uvicorn, cryptography, boto3 (AWS SDK)
* Frontend: React, Vite, Workbox, Dexie.js (IndexedDB wrapper)

**Storage**:
* Relational: PostgreSQL (version 16+) with row-level pessimistic locking (`SELECT ... FOR UPDATE`)
* Local Cache: IndexedDB via Dexie.js

**Testing**:
* Backend: pytest, pytest-asyncio, HTTPX
* Frontend: Vitest, React Testing Library, Playwright (for PWA / offline testing)

**Target Platform**: Cloud (AWS: S3 + CloudFront for Frontend, ECS / AppRunner + API Gateway for Backend, RDS for PostgreSQL, AWS KMS for key management)

**Project Type**: Decoupled Web Application (Frontend React PWA + Backend REST API)

**Performance Goals**:
* Database search latency < 2.0s under 100 concurrent users (NFR-001)
* PWA page load time < 3.0s over Nigerian 3G/4G networks (NFR-002)

**Constraints**:
* Strict NDPR (Nigeria Data Protection Regulation) compliance for sensitive medical records
* No administrator visibility into clinical notes, diagnoses, or prescriptions
* Resilience to local network disconnections (2-hour read-only scheduling cache)
* Bypass Nigerian carrier DND rules using Termii local SMS

**Scale/Scope**:
* 3 pilot branches (scaling to 10-15 branches)
* 4-month MVP development timeline

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

* **Principle I: Relational Data Integrity and Concurrency Control**
  * *Status*: ✅ Passed
  * *Verification*: PostgreSQL 16+ selected as primary datastore; row-level pessimistic locking (`with_for_update()`) pseudo-code defined for appointment slots.
* **Principle II: Local Resilience and Offline-First PWA Client**
  * *Status*: ✅ Passed
  * *Verification*: Vite + React SPA PWA using Workbox for shell caching and Dexie.js/IndexedDB for local 2-hour offline scheduling storage.
* **Principle III: Zero-Trust Application-Level Column Encryption**
  * *Status*: ✅ Passed
  * *Verification*: AES-256-GCM encryption at the backend layer with AWS KMS envelope encryption; system admins cryptographically excluded.
* **Principle IV: Pluggable Integration & Multi-Provider Failover**
  * *Status*: ✅ Passed
  * *Verification*: Strategy Pattern abstraction for `NotificationService`; asynchronous routing queue with failover order: WhatsApp -> Termii SMS -> Infobip SMS.
* **Principle V: Comprehensive Mandatory Testing Discipline**
  * *Status*: ✅ Passed
  * *Verification*: TDD mandatory; contract, integration, and unit tests are included in the setup plan; mock KMS and network test helpers specified.

## Project Structure

### Documentation (this feature)

```text
specs/001-core-architecture/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── appointments.json
│   └── clinical_records.json
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
├── alembic/             # Database migrations
├── src/
│   ├── api/             # REST API endpoints
│   ├── core/            # Config, security, encryption
│   ├── models/          # SQLModel/SQLAlchemy database models
│   ├── services/        # Strategy-based NotificationService
│   └── main.py          # Application entrypoint
└── tests/
    ├── unit/            # Unit tests (encryption, schemas)
    ├── integration/     # Integration tests (pessimistic locking, failover)
    └── contract/        # Contract tests (endpoint payload schemas)

frontend/
├── src/
│   ├── components/      # UI components (Offline banner, layout)
│   ├── pages/           # Receptionist and doctor dashboards
│   ├── services/        # API client and Dexie.js database sync
│   └── main.tsx
└── tests/
    ├── unit/
    └── e2e/             # Playwright offline tests
```

**Structure Decision**: Decoupled Web Application layout (Option 2 from template) with `backend/` and `frontend/` directories under the repository workspace root.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Application-Level Column Encryption | Meet strict NDPR compliance and prevent database administrators from viewing clinical notes. | Database transparent data encryption (TDE) is simpler but exposes clinical notes to DB administrators. |
| Multi-Gateway Failover Engine | Guarantee delivery of booking reminders over unstable carrier networks and DND blocks. | Single notification gateway is simpler but risks high failure rates due to DND and outages. |
| Browser-side IndexedDB Caching | Keep clinic scheduling functional for 2 hours during local internet outages. | Online-only app is simpler but fails to meet branch operational reliability constraints. |
