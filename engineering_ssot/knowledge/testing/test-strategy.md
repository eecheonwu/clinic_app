# Test Strategy — Clinic Modernization Platform (CMP)

**Version**: 1.7
**Last Updated**: 2026-07-31

---

## Test Pyramid

| Layer | Tools | Target Coverage |
|-------|-------|-----------------|
| Unit | pytest, pytest-asyncio | 80%+ |
| Integration | pytest, httpx.AsyncClient | 70%+ |
| E2E | Playwright | Critical paths |
| Performance | Locust (planned) | NFR-001, NFR-002 |

---

## Test Environments

| Environment | Database | Redis | KMS | Notes |
|-------------|----------|-------|-----|-------|
| Development | SQLite (test) | Local Redis | Mock KMS | Fast feedback |
| CI | PostgreSQL 16 | Redis container | Mock KMS | Parallel test execution |
| Staging | RDS PostgreSQL | ElastiCache | Real KMS | Full integration |

---

## Test Categories

### Unit Tests (Task 4.1) ✅ COMPLETE

- **AuthenticationService**: JWT generation, token refresh, role extraction
- **OTPService**: Code generation, validation, rate limiting (3 req/15min), max attempts (5), expiry (10min), single-use
- **OTP Delivery System**: OTP generation, hashing, verification, rate limiting, notification delivery via WhatsApp/SMS, failover chain, complete OTP flow integration (Task 6.5)
- **OTP Delivery Fix Round 2**: No User lookup required for registration flow, WhatsApp URL construction fix, Celery configuration fix
- **SchedulingEngine**: Slot validation, conflict detection, pessimistic lock behavior
- **ClinicalRecordService**: Encryption/decryption round-trip, KMS key caching, error handling
- **NotificationService**: Strategy Pattern routing, failover chain, idempotency
- **CancellationPenaltyEngine**: Tier calculation, emergency exemption, staff override
- **EmailClient Provider (Checkpoint 1 / Task 4.3)**: EmailClient initialization & provider interface, send via console/mock provider with NotificationLog audit, invalid recipient validation, `NotificationService.send()` interface, `EmailVerificationToken` model attributes, `send_auth_email` Celery task, `send_email_notification` Celery task, Alembic migration 0007 structure — **8/8 passed** ✅

### Integration Tests (Task 6.2) ✅ COMPLETE

- **Booking Flow**: End-to-end appointment booking with conflict detection
- **Concurrent Booking**: Multiple simultaneous booking requests handled correctly
- **Slot Availability**: Query and filtering of available time slots
- **Reschedule Flow**: Appointment rescheduling with conflict detection
- **Cancellation Flow**: Three-tier cancellation policy (within 2 hours, warning, staff override)
- **Clinical Encryption**: AES-256-GCM encryption with random IV
- **Security Properties**: Key validation, integrity checks, no plaintext in storage
- **Authorization**: Patient cannot create clinical records, doctors can access any record
- **Audit Logging**: Audit logs created for clinical record operations

### E2E Tests (Task 6.3) ✅ COMPLETE

- **Patient journey**: register → verify → book → cancel
- **Doctor journey**: view schedule → write notes → release lab results
- **Receptionist journey**: walk-in → check-in → override
- **Offline resilience**: disconnect → read cache → reconnect

### Performance Tests (Task 6.4) ✅ COMPLETE

- /available-slots < 2.0s at 100 concurrent users (NFR-001)
- PWA load < 3.0s on 3G/4G (NFR-002)
- Pessimistic lock acquisition < 3.0s timeout
- Encryption audit: AES-256 key size, IV size, tag size, random IV, integrity check

---

## Test Execution

```bash
# Run all tests
pytest tests/ -v --cov=src/backend

# Run specific module
pytest tests/test_auth.py -v

# Run integration tests
pytest tests/integration/ -v

# Run performance tests
pytest tests/load/ -v

# Run with coverage report
pytest tests/ --cov=src/backend --cov-report=html
```

---

## Coverage Targets

| Module | Target | Current (2026-07-30) |
|--------|--------|------------------------|
| src/backend/core/config.py | 95% | 98% ✅ |
| src/backend/main.py | 90% | 86% ⚠️ |
| src/backend/api/v1/admin/router.py | 80% | 72% ⚠️ |
| src/backend/services/auth_service.py | 80% | 77% ⚠️ |
| src/backend/services/report_service.py | 90% | 100% ✅ |
| src/backend/utils/encryption.py | 80% | 78% ⚠️ |
| src/backend/models/ | 95% | 93-100% ✅ |
| **Total** | **80%** | **67%** ⚠️ |

---

## Known Gaps

1. Router endpoints (appointments, clinical_records, auth) need database integration tests
2. Frontend E2E tests implemented (18 tests in src/frontend/tests/e2e/)
3. Performance benchmarks completed (20 load tests + 11 E2E performance tests)
4. Security tests completed (7 encryption audit tests + 2 KMS configuration tests)
5. OTP delivery system tests completed (13 tests in test_otp_delivery.py)
6. OTP delivery fix round 2 completed (5 tests in test_otp_delivery_fix.py)
7. Email provider unit tests completed — 8 tests in test_email_provider.py (Checkpoint 1) ✅
8. Patient registration email endpoints (Tasks 2.2–2.7) not yet implemented — integration tests pending (Checkpoint 2)

---

## OTP Delivery Fix Round 2 Tests (5 tests)

### Test Coverage

- **TestSendOtpTaskNoUser** (3 tests): Static analysis of send_otp_task source code
  - test_send_otp_task_source_no_user_lookup - Verifies no User query in task
  - test_send_otp_task_source_no_user_not_found_return - Verifies no "User not found" return
  - test_send_otp_task_inner_logic_uses_otp_phone_number - Verifies otp.phone_number usage

- **TestWhatsAppUrlConstruction** (3 tests): WhatsApp URL construction verification
  - test_whatsapp_url_no_extra_v1 - Verifies no extra /v1/ path segment
  - test_whatsapp_url_with_real_api_url - Verifies correct URL with real API URL
  - test_whatsapp_url_source_no_v1 - Static analysis of source code

- **TestCeleryConfig** (2 tests): Celery configuration verification
  - test_celery_include_path - Verifies include path is "workers.tasks"
  - test_celery_task_routes - Verifies task routes use explicit names

- **TestOtpDeliveryWithoutUser** (2 tests): Integration test for OTP delivery without User
  - test_orchestrator_send_otp_uses_phone_number - Verifies direct phone number usage
  - test_orchestrator_send_otp_no_user_required - Verifies no User lookup required

---

## Recommendations

1. **Router integration tests added** for appointments, clinical_records, and auth endpoints ✅
2. **Integration tests added** for booking flow and clinical encryption (Task 6.2) ✅
3. **E2E tests added** for patient journey and offline mode (Task 6.3) ✅
4. **Performance tests added** for NFR-001 and NFR-002 (Task 6.4) ✅
5. **OTP delivery tests added** for notification system (Task 6.5) ✅
6. **OTP delivery fix round 2 tests added** for Celery, WhatsApp URL, and task refactor ✅
7. **Email provider tests added** for EmailClient, EmailVerificationToken model, Celery email tasks, and Alembic migration 0007 (Checkpoint 1) ✅
8. **Set up test database** for full integration testing
9. **Add integration tests** for patient email registration flow (Checkpoint 2 — Task 4.4)