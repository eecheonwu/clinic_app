# Research Report: Core Architecture Setup

## Decision 1: PostgreSQL Relational Database with Row-Level Pessimistic Locking
* **Decision**: Use PostgreSQL (version 16+) as the primary datastore, using SQLAlchemy / SQLModel in FastAPI and direct row-level locks via `with_for_update()` during appointment booking.
* **Rationale**: The core requirement is to prevent doctor schedule double-booking. Pessimistic locks prevent race conditions at the database tier before inserts occur.
* **Alternatives Considered**:
  - MongoDB: Rejected because transaction locks across collections (e.g. availability slots vs appointments) require complex distributed lock managers or multi-document transactions with low performance.

## Decision 2: React + Vite PWA with Dexie.js (IndexedDB)
* **Decision**: Frontend client built as a React SPA with Vite, compiling to static assets deployed on AWS S3/CloudFront. Uses service worker caching via Workbox and Dexie.js for IndexedDB caching.
* **Rationale**: Registers a client-side database to sync and cache schedules daily. If connectivity drops, clinic workers can read schedules for at least 2 hours offline. CloudFront edge caching ensures page load < 3s.
* **Alternatives Considered**:
  - Next.js: Rejected because Server-Side Rendering (SSR) requires Node.js hosting infrastructure, increasing cost/failure points, and complicates offline PWA routing.

## Decision 3: Application-Level Column Encryption (AES-256-GCM + AWS KMS)
* **Decision**: Encrypt restricted clinical fields (`notes`, `diagnosis`, `prescriptions`) in the backend FastAPI application before database persistence. Key management uses AWS KMS wrapping keys with short-term local DEK caching in memory (envelope encryption).
* **Rationale**: Complies with NDPR and secures patient privacy against administrative access. System admins and DB admins see only encrypted ciphertext.
* **Alternatives Considered**:
  - Database Transparent Data Encryption (TDE): Rejected because it decrypts data transparently, allowing DB admins to query sensitive tables in plaintext.

## Decision 4: Pluggable Notification Layer with Strategy Pattern and Multi-Provider Failover
* **Decision**: Decouple notification logic using Strategy Pattern (`NotificationService` interface and adapters: `WhatsAppCloudAPIClient`, `TermiiSMSClient`, `InfobipSMSClient`). Runs asynchronously via task queue (Redis) with failover sequence: WhatsApp -> Termii SMS -> Infobip SMS.
* **Rationale**: Maximizes delivery rates under Nigerian DND carrier routing rules and instability. WhatsApp is cheap/preferred, Termii provides DND-bypass local SMS, and Infobip is a backup.
* **Alternatives Considered**:
  - Single Provider (e.g. Infobip Only): Rejected because of single point of failure and poor reliability with Nigerian DND carrier blocks.

## Decision 5: Mandatory Testing Framework with Mocks
* **Decision**: Setup mandatory testing using pytest for backend and Vitest/Playwright for frontend. Include mock providers for AWS KMS, WhatsApp API, Termii SMS, and Infobip SMS to allow localized TDD execution.
* **Rationale**: Strictly ensures encryption cycles, locking behavior, and notification failovers work as designed before deployment.
* **Alternatives Considered**:
  - Manual QA: Rejected due to high regression risk for security and locking algorithms.
