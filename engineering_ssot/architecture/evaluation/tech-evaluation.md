# CMP — Technology Evaluation

**Source**: Technology Evaluation (2026-06-04)

---

## Technology Decisions

| Area | Decision | Status |
|---|---|---|
| Frontend | Vite + React PWA (SPA + Service Workers + Dexie.js/IndexedDB) | **Adopt** |
| Backend | FastAPI (Python 3.12+) | **Adopt** |
| Database | PostgreSQL 16+ (AWS RDS or Supabase) | **Adopt** |
| Offline Caching | Workbox (Service Worker) + Dexie.js (IndexedDB) | **Adopt** |
| Security/Encryption | Application-level AES-256-GCM + AWS KMS | **Adopt** |
| Notifications | Pluggable NotificationService (Termii + Infobip + WhatsApp API) | **Adopt** |
| Frontend (rejected) | Next.js App Router (SSR) | **Reject** |
| Backend (rejected) | NestJS (TypeScript/Node.js) | **Reject** |
| Database (rejected) | MongoDB (NoSQL) | **Reject** |

---

## Alternatives Considered & Trade-offs

### Frontend: Vite + React PWA vs Next.js

| Attribute | Vite + React PWA | Next.js (Rejected) |
|---|---|---|
| Offline PWA | Native Service Worker control; simple | Highly complex with SSR boundaries |
| Hosting cost | Near-zero (S3 + CloudFront CDN) | Higher (Node server on ECS/Lambda) |
| Page load speed | Sub-3s on mobile via CDN | Good but SSR adds complexity |
| SEO | Low (irrelevant; all behind auth) | Excellent (unnecessary) |
| Effort | Low | High |

**Decision rationale**: NFR-004 (2-hour offline cache) is the decisive constraint. A static SPA with Service Workers is the only clean implementation path.

### Backend: FastAPI vs NestJS

| Attribute | FastAPI (Python 3.12+) | NestJS (Rejected) |
|---|---|---|
| Development speed | High (minimal boilerplate) | Medium (heavy boilerplate) |
| Async throughput | High (native async/await) | High (Node.js event loop) |
| AI/LLM Phase 2 readiness | High (Python ecosystem, pgvector) | Medium (TypeScript ecosystem) |
| Type safety | Pydantic models | TypeScript strict mode |
| Effort | Low | High |

**Decision rationale**: 4-month timeline demands minimal overhead. Python is industry standard for Phase 2 LLM integration (AI-001–AI-004).

### Database: PostgreSQL vs MongoDB

| Attribute | PostgreSQL (Adopted) | MongoDB (Rejected) |
|---|---|---|
| Transactional locking | Native `SELECT ... FOR UPDATE` | Requires app-level distributed lock |
| Relational integrity | Full ACID | Limited across collections |
| FR-004 / FR-019 support | Direct | Fragile application workarounds |
| Phase 2 vector search | pgvector extension | Atlas Vector Search (lock-in) |
| Effort | Low | Medium (custom locking required) |

**Decision rationale**: Scheduling integrity (BG-004, FR-004, FR-019) is non-negotiable. PostgreSQL provides it at the DB layer.

### Security: App-Level Encryption vs Database TDE

| Attribute | AES-256-GCM + AWS KMS (Adopted) | TDE (Rejected) |
|---|---|---|
| NFR-008 (Admin separation) | **Satisfied** — DB admins see only ciphertext | **Fails** — DB users can read plaintext |
| NDPR compliance | Full | Partial |
| SQL search on encrypted fields | Not possible (use metadata search) | Fully available |
| Performance | Slight overhead (mitigated by envelope encryption + DEK caching) | Zero overhead |

---

## Risks Identified

| Area | Risk | Mitigation |
|---|---|---|
| Frontend | Heavy JS bundles degrade older devices | Lazy-loading, code splitting |
| Frontend | Service Worker stale cache | Strict cache invalidation strategy |
| Backend | Disorganized codebase (spaghetti) | Enforce Hexagonal / Clean Architecture from day one |
| Database | Poor index design degrades search to >2s | EXPLAIN plan analysis, strict indexing guidelines |
| Database | Schema migrations cause downtime | Backward-compatible migrations (Alembic) |
| Security | KMS key compromise blocks all clinical access globally | KMS key rotation policy, secondary region backup |
| Security | Encryption latency per API request | Envelope encryption: DEK cached in application memory |
| Notifications | Message duplication on failover false positives | Idempotency tracking in NotificationLog |

---

## Assumptions

- Patients have active mobile data access to load the lightweight PWA.
- WhatsApp Business Cloud API provides reliable delivery in Nigeria; failures trigger SMS fallback.
- Local power outages are mitigated by clinic generators/UPS; offline cache provides read-only resiliency.
- Medical staff will adopt digital note entry.

---

## Tradeoff Matrix Summary

| Quality Attribute | FastAPI + React PWA + PostgreSQL | Next.js + NestJS + MongoDB |
|---|---|---|
| Development Speed | **High** | Medium |
| Transactional Safety | **High** (DB-level locks) | Low (app-level validation) |
| Offline Resiliency | **High** (Service Worker + IndexedDB) | Low/Medium (SSR conflicts) |
| NDPR/Security | **High** (column encryption) | Medium (TDE only) |
| AI Integration (Phase 2) | **High** (Python + pgvector) | Medium |
| Initial Cloud Cost | **Low** (S3/CDN + ECS Fargate) | Medium (Node cluster) |
