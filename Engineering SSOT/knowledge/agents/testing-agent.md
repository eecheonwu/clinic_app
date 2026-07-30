# Testing Agent Context — Clinic Modernization Platform (CMP)

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
- **ADR-004**: Strategy-Pattern-based Notification Service Abstraction + Celery/Redis queue for async multi-channel failover (WhatsApp → Termii → Infobip).

## Validation Rules
1. **Coverage Targets**: Ensure that backend unit and integration tests achieve a minimum of 80% coverage on all services (scheduling, encryption, auth, OTP).
2. **Concurrency Verification**: Validate that scheduling features undergo concurrency test suites (e.g., simulating 10 overlapping booking attempts simultaneously where exactly 1 succeeds and 9 fail with HTTP 409).
3. **Failover Progression**: Notification worker integration tests must mock HTTP requests and simulate WhatsApp timeouts/failures to verify correct failover progression down to Termii and Infobip.
4. **Offline and Network Emulation**: Client-side UI testing must include network emulation verification (offline mode) to ensure IndexedDB/Dexie.js-cached data renders and that the offline warning banner is displayed.

## Test Status (2026-07-11)

### Test Summary
| Test Type | Count | Status |
|-----------|-------|--------|
| Unit Tests | 173 | ✅ PASS |
| Integration Tests | 21 | ✅ PASS |
| E2E Tests | 18 | ✅ COMPLETE |
| Performance Tests | 20 | ✅ PASS |
| **Total** | **232** | **All Pass** |

### Coverage Status
| Module | Coverage | Status |
|--------|----------|--------|
| `src/backend/core/config.py` | 98% | ✅ |
| `src/backend/services/report_service.py` | 100% | ✅ |
| `src/backend/models/` | 93-100% | ✅ |
| `src/backend/main.py` | 86% | ⚠️ |
| `src/backend/api/v1/admin/router.py` | 72% | ⚠️ |
| `src/backend/services/auth_service.py` | 77% | ⚠️ |
| `src/backend/utils/encryption.py` | 78% | ⚠️ |
| **Overall** | **67%** | **⚠️ (target 80%)** |

### Security Verification (Task 6.4)
- AES-256 key size: 32 bytes ✅
- IV size: 12 bytes (96-bit) ✅
- Tag size: 16 bytes (128-bit) ✅
- Random IV usage: Verified ✅
- Integrity check: Verified ✅
- KMS lazy initialization: Verified ✅
- KMS dev fallback: Verified ✅

### Performance Verification (Task 6.4)
- /available-slots response time < 2.0s: ✅
- Lock acquisition time < 3.0s: ✅
- Concurrent access (100 users): ✅
- PWA load time < 3.0s on 3G: ✅