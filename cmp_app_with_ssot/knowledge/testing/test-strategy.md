# Test Strategy — Clinic Modernization Platform (CMP)

**Version**: 1.4
**Last Updated**: 2026-07-12

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
- **SchedulingEngine**: Slot validation, conflict detection, pessimistic lock behavior
- **ClinicalRecordService**: Encryption/decryption round-trip, KMS key caching, error handling
- **NotificationService**: Strategy Pattern routing, failover chain, idempotency
- **CancellationPenaltyEngine**: Tier calculation, emergency exemption, staff override

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

| Module | Target | Current (2026-07-12) |
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
2. Worker tasks (celery_app.py, tasks.py) need separate testing infrastructure
3. Frontend E2E tests implemented (18 tests in src/frontend/tests/e2e/)
4. Performance benchmarks completed (20 load tests + 11 E2E performance tests)
5. Security tests completed (7 encryption audit tests + 2 KMS configuration tests)
6. OTP delivery system tests completed (13 tests in test_otp_delivery.py)

---

## E2E Test Details (Task 6.3)

### Patient Journey Tests (12 tests)

- **TC-PJ-01**: Full patient registration flow
- **TC-PJ-02**: OTP verification flow
- **TC-PJ-03**: Staff login flow
- **TC-PJ-04**: View appointments list
- **TC-PJ-05**: Book new appointment flow (branch → doctor → slot → confirm)
- **TC-PJ-06**: Cancel appointment with penalty warning
- **TC-PJ-07**: Cancel appointment - dismiss confirmation
- **TC-PJ-08**: Login form validation - empty fields
- **TC-PJ-09**: Login form validation - invalid credentials
- **TC-PJ-10**: Unauthenticated user redirected to login
- **TC-PJ-11**: Logout clears session and redirects
- **TC-PJ-12**: Navigate between booking flow steps

### Offline Mode Tests (6 tests)

- **TC-OM-01**: Dashboard loads with cached appointments online
- **TC-OM-02**: Offline banner appears when network is disconnected
- **TC-OM-03**: Cached appointments viewable in offline mode
- **TC-OM-04**: Offline banner disappears when back online
- **TC-OM-05**: IndexedDB cache is cleared on logout
- **TC-OM-06**: Login page accessible when offline

### Performance Tests (11 tests)

- **TC-PERF-01**: Page load time under 3G simulation
- **TC-PERF-02**: Login page load time under 3G simulation
- **TC-PERF-03**: Register page load time under 3G simulation
- **TC-PERF-04**: Service worker registration
- **TC-PERF-05**: PWA manifest exists
- **TC-PERF-06**: Static assets are cached
- **TC-PERF-07**: Response time for API calls
- **TC-PERF-08**: Bundle size check
- **TC-LH-01**: Performance metrics collection
- **TC-LH-02**: Accessibility check - form labels
- **TC-LH-03**: Best practices - HTTPS check

---

## Performance Test Details (Task 6.4)

### Backend Load Tests (20 tests)

- **TestPerformanceThresholds** (3 tests): Response time, concurrent users, lock timeout configuration
- **TestAvailableSlotsLoad** (3 tests): Response time, concurrent access, performance with many appointments
- **TestLockAcquisitionPerformance** (2 tests): Lock timeout, acquisition time
- **TestConcurrentBookingPerformance** (1 test): Concurrent booking under load
- **TestEncryptionAudit** (7 tests): Random IV, ciphertext, round-trip, integrity, key/IV/tag sizes
- **TestKMSConfiguration** (2 tests): Lazy initialization, dev fallback
- **TestAPIResponseTime** (2 tests): Health check, root endpoint

### Frontend Performance Tests (11 tests)

- **TC-PERF-01** to **TC-PERF-08**: Page load times, service worker, PWA manifest, caching, API response
- **TC-LH-01** to **TC-LH-03**: Lighthouse audit simulation (performance metrics, accessibility, best practices)

---

## OTP Delivery System Tests (Task 6.5)

### Test Coverage (13 tests)

- **OTP Generation** (4 tests):
  - test_generate_otp_length - Verifies 6-digit OTP
  - test_generate_otp_uniqueness - Verifies uniqueness
  - test_hash_otp - Verifies bcrypt hashing
  - test_verify_otp - Verifies hash verification

- **OTP Creation** (2 tests):
  - test_create_otp_returns_tuple - Verifies tuple return (record, plain_text)
  - test_create_otp_rate_limit - Verifies rate limiting (3 req/15min)

- **OTP Verification** (3 tests):
  - test_verify_otp_success - Successful verification
  - test_verify_otp_invalid_code - Invalid code handling
  - test_verify_otp_max_attempts - Max attempts (5) enforcement

- **Notification Delivery** (3 tests):
  - test_send_otp_via_whatsapp - WhatsApp delivery
  - test_send_otp_fallback_to_sms - SMS fallback
  - test_send_otp_all_providers_fail - All providers fail handling

- **Integration** (1 test):
  - test_complete_otp_flow - End-to-end OTP flow

**Test Results**: 13 passed, 11 warnings in 5.48s

---

## Recommendations

1. **Router integration tests added** for appointments, clinical_records, and auth endpoints ✅
2. **Integration tests added** for booking flow and clinical encryption (Task 6.2) ✅
3. **E2E tests added** for patient journey and offline mode (Task 6.3) ✅
4. **Performance tests added** for NFR-001 and NFR-002 (Task 6.4) ✅
5. **OTP delivery tests added** for notification system (Task 6.5) ✅
6. **Set up test database** for full integration testing
7. **Create separate test infrastructure** for Celery worker tasks