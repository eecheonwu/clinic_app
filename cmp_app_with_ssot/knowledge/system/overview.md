# CMP — System Overview

**Source**: Technical Specification v1.0 (Draft, 2026-06-04)  
**Target Release**: Phase 1 MVP (4-month timeline)

---

## System Description

Secure, cloud-hosted clinic management system. Decoupled frontend/backend architecture:
- **Frontend**: Vite + React PWA (static SPA)
- **Backend**: FastAPI (Python 3.12+) async REST API
- **Database**: PostgreSQL 16+ (AWS RDS)
- **Queue**: Redis + Celery (async background tasks)
- **Security**: Application-level AES-256-GCM encryption + AWS KMS
- **Notifications**: Pluggable failover chain (WhatsApp → Termii SMS → Infobip SMS)

---

## System Goals

| ID | Goal |
|---|---|
| G-001 | Pessimistic locking — eliminate doctor double-booking |
| G-002 | Sub-3.0s page load over Nigerian 3G/4G via static PWA |
| G-003 | 2-hour offline read-only cache for scheduling dashboards |
| G-004 | Application-layer encryption of patient records (hidden from DB/cloud admins) |
| G-005 | Automated notification delivery with WhatsApp→Termii→Infobip failover chain |

---

## Non-Goals (Phase 1)

- No video/audio telemedicine
- No Paystack/Flutterwave payment transaction routing (DB schema supports it; routing deferred to Phase 2)
- No native Android/iOS apps (responsive web only)
- No automated clinical diagnosis or AI treatment recommendations

---

## Architecture Style

**Decoupled SPA + Async REST API**

- React PWA (client-side SPA) communicates with FastAPI backend over HTTPS / TLS 1.3.
- All API traffic routed through AWS API Gateway (rate limiting, auth enforcement).
- Background tasks (notifications, OTP delivery) executed asynchronously via Celery + Redis.
- Database interactions use SQLAlchemy/SQLModel ORM with raw pessimistic locks for booking operations.

---

## Key Design Decisions (Cross-reference ADRs)

| ADR | Decision |
|---|---|
| ADR-001 | PostgreSQL as primary datastore — relational integrity + pessimistic locks |
| ADR-002 | Vite + React PWA — static SPA with Service Worker offline cache |
| ADR-003 | Application-level AES-256-GCM column encryption — clinical data separation from admins |
| ADR-004 | Pluggable notification abstraction (Strategy Pattern) — WhatsApp→Termii→Infobip failover |

---

## Failure Mode Responses

| Failure | System Response | Recovery |
|---|---|---|
| DB Lock Contention | HTTP 409 after 3.0s transaction timeout | Client prompts user to select another slot |
| Offline Transition | Browser detects disconnect; blocks writes | Dashboard loads from IndexedDB cache (read-only, 2h) |
| WhatsApp API Offline | Worker catches error; logs failure | Failover worker sends via Termii SMS immediately |
| AWS KMS Unavailable | HTTP 503; block encrypted record creation/reads | Clinical notes never saved in plaintext; temporary lock |

---

## Security Architecture

- **RBAC**: FastAPI security scopes; JWT tokens carry user role.
- **KMS Key Policy**: `kms:Decrypt`/`kms:Encrypt` scoped strictly to backend application IAM role. Root/admin IAM roles explicitly denied.
- **Clinical Data Separation**: DB admins only see ciphertext — NFR-008 satisfied cryptographically.
- **Immutable Audit Trail**: `security_audit_logs` record inserted within same PostgreSQL transaction as any clinical record change.
- **TLS 1.3**: All client-server communication.

---

## Observability

- Structured JSON logs with `correlation_id` header tracing requests across API → queue → DB.
- DB query duration logged to Datadog/CloudWatch; alarm triggers if search >2.0s (NFR-001).
- `NotificationLog` table tracks delivery metrics (latency from appointment creation to delivery).

---

## Rollout Plan

1. Alembic schema migrations (backward-compatible: nullable first → populate → constrain).
2. PWA static shell hosted on AWS S3/CloudFront (staging DNS).
3. Phased clinic rollout: Branch A (Week 1) → Branch B (Week 3) → Branch C (Week 5).
4. Offline cache validation: simulate workstation disconnection tests.

---

## Resolved Technical Decisions

| Question | Resolution | Date |
|---|---|---|
| OQ-001: KMS Access Policies | AWS KMS Key Policies scoped to backend application IAM role | 2026-06-04 |
| OQ-002: OTP Route Channel | WhatsApp-first with 15-second timeout → SMS fallback (Termii/Infobip) | 2026-06-04 |
