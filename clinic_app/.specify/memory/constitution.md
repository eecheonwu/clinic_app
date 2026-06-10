<!--
SYNC IMPACT REPORT
==================
Version change: [PROJECT_NAME] Constitution Template -> v1.0.0
Modified Principles:
- [PRINCIPLE_1_NAME] -> I. Relational Data Integrity & Pessimistic Concurrency Control
- [PRINCIPLE_2_NAME] -> II. Local Resilience and Offline-First PWA Client
- [PRINCIPLE_3_NAME] -> III. Zero-Trust Application-Level Column Encryption
- [PRINCIPLE_4_NAME] -> IV. Pluggable Notification Service with Multi-Provider Failover
- [PRINCIPLE_5_NAME] -> V. Comprehensive Mandatory Testing Discipline
Added Sections:
- Technology Stack Constraints
- Development Workflow and Quality Gates
Removed Sections:
- None
Templates requiring updates:
- .specify/templates/tasks-template.md: ✅ updated (made testing tasks mandatory across all user stories)
- .specify/templates/spec-template.md: ✅ updated (no changes needed, already aligns)
- .specify/templates/plan-template.md: ✅ updated (no changes needed, dynamic check aligns)
Follow-up TODOs:
- None (All placeholders successfully resolved)
-->

# Clinic Modernization Platform (CMP) Constitution

## Core Principles

### I. Relational Data Integrity and Pessimistic Concurrency Control
The application MUST use PostgreSQL (version 16+) as the primary relational datastore. All scheduling and booking transactions MUST employ database-level pessimistic locking (`SELECT ... FOR UPDATE`) to eliminate booking race conditions and double-bookings. Database schema changes MUST be managed through structured SQL migrations via an ORM (SQLAlchemy/SQLModel).
* **Rationale**: High-concurrency booking of doctor slots requires database-tier synchronization rather than application-tier distributed locks to ensure zero scheduling conflicts.

### II. Local Resilience and Offline-First PWA Client
The frontend MUST be structured as a Progressive Web App (PWA) built with Vite + React. The application MUST use service workers (configured via Workbox) to cache static shell assets. Local database queries and scheduling caches MUST use Dexie.js (IndexedDB wrapper). The receptionist and doctor dashboards MUST maintain a 2-hour offline read-only local scheduling cache to remain resilient to local ISP or power failures. A clear "Offline Mode" visual indicator MUST be displayed when offline.
* **Rationale**: High local network volatility in Nigeria requires that clinic staff retain access to schedules during connectivity drops without server-side page rendering dependencies.

### III. Zero-Trust Application-Level Column Encryption
All sensitive patient clinical data (such as consultation notes, diagnoses, and prescriptions) MUST be encrypted before persistence. Encryption MUST be performed at the application level (FastAPI) using AES-256-GCM. Encryption keys (DEK) MUST be managed using AWS KMS with envelope encryption to avoid exposing plaintext keys in database storage or backups. System and database administrators MUST NOT have access to decrypt or read patient clinical records. Only users authenticated with clinical roles (e.g. Doctors) are permitted to request decryption.
* **Rationale**: In compliance with NDPR rules, database compromises or administrative access must not expose private patient clinical information.

### IV. Pluggable Integration & Multi-Provider Failover
The notification layer MUST be designed using the Strategy Pattern, abstracting third-party APIs behind a pluggable `NotificationService` interface. Notification operations MUST be executed asynchronously using worker queues (e.g., Redis task queue). The system MUST implement a failover delivery chain: first attempting WhatsApp Business Cloud API, failing over to Termii SMS, and then to Infobip SMS if Termii fails. Every dispatch attempt, gateway status, and error code MUST be recorded in a dedicated `NotificationLog` database table.
* **Rationale**: Avoids vendor lock-in and maximizes booking reminder delivery rates despite Nigerian mobile carrier instability and DND restrictions.

### V. Comprehensive Mandatory Testing Discipline
Automated testing is MANDATORY for all features. Developers MUST use a Test-Driven Development (TDD) cycle for core business logic, writing failing tests before implementation. Test suites MUST verify concurrency locks (pessimistic locking behavior), offline caching, column encryption/decryption cycles with KMS, and failover notifications routing. Every User Story MUST include independent contract, integration, and unit tests to ensure that each incremental deliverable is fully functional and stable on its own.
* **Rationale**: Quality control, especially for complex features like encrypted columns, failovers, and race-condition locking, requires strict automated verification to prevent regression.

## Technology Stack Constraints
The Clinic Modernization Platform (CMP) is constrained to the following tech stack:
* **Backend**: FastAPI (Python 3.12+), SQLAlchemy/SQLModel.
* **Frontend**: React (Vite, Workbox, Dexie.js for IndexedDB).
* **Database**: PostgreSQL 16+ (deployed on managed AWS RDS or Supabase).
* **Encryption**: `cryptography` library (AES-256-GCM), AWS KMS SDK.
* **Background Tasks**: Redis for task queue (FastAPI BackgroundTasks or Celery).
* **External APIs**: WhatsApp Business Cloud API, Termii SMS, Infobip SMS.

## Development Workflow and Quality Gates
* **Branch Naming**: All feature branches MUST be named using the `[###-feature-name]` format.
* **CI Pipeline**: Pull requests MUST pass all static analysis (linting, formatting) and all automated test suites prior to merging.
* **TDD Enforcement**: Write tests first, verify failure, then write minimal implementation code to pass.
* **Security Scan**: Dependencies and code MUST be scanned for security vulnerabilities (e.g. `npm audit`, `safety`, `bandit`) before releases.

## Governance
* This constitution is the primary source of truth for design constraints and engineering standards.
* All pull requests and peer reviews MUST verify compliance with these core principles.
* Any deviations from these principles must be documented as architectural decisions (ADRs) and require explicit approval by the AI Architect and Clinic Owner.
* Amendments to the constitution MUST trigger a semantic version increment:
  - **MAJOR**: Backward incompatible governance/principle changes.
  - **MINOR**: New principles or expanded guidance.
  - **PATCH**: Typos, minor clarifications.
* Governance dates MUST be kept up to date in the format YYYY-MM-DD.

**Version**: 1.0.0 | **Ratified**: 2026-06-10 | **Last Amended**: 2026-06-10
