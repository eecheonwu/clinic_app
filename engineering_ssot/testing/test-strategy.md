# Test Strategy — Clinic Modernization Platform (CMP)

**Version**: 2.0  
**Last Updated**: 2026-08-02  

---

## Test Pyramid

| Layer | Tools | Target Coverage | Status |
|-------|-------|-----------------|--------|
| Unit | pytest, pytest-asyncio | 80%+ | ✅ COMPLETE |
| Integration | pytest, httpx.AsyncClient / TestClient | 70%+ | ✅ COMPLETE |
| E2E | Playwright | Critical paths | ✅ COMPLETE |
| Performance | Locust, pytest load tests | NFR-001, NFR-002 | ✅ COMPLETE |

---

## Test Environments

| Environment | Database | Redis | KMS | Notes |
|-------------|----------|-------|-----|-------|
| Development | SQLite / AsyncMock | Local Redis / Mock | Mock KMS | Fast feedback |
| CI | PostgreSQL 16 | Redis container | Mock KMS | Parallel test execution |
| Staging | RDS PostgreSQL | ElastiCache | Real KMS | Full integration |

---

## Test Categories

### Unit & Integration Tests (Checkpoints 1–7) ✅ COMPLETE

- **AuthenticationService**: JWT generation (`aud: "patient"`, `aud: "staff"`), token refresh, audience claim verification, email-based patient registration, token invalidation, bcrypt token verification, password policy enforcement.
- **Audience & Security Boundaries (`test_jwt_audience.py`)**: 7 tests verifying `aud: "patient"` vs `aud: "staff"` claim injection and `RoleChecker` security boundary enforcement (HTTP 403 on cross-boundary requests).
- **Patient Auth & Resend (`test_auth_patient.py`)**: 53 tests covering `POST /auth/patient/register`, `POST /auth/patient/verify-email`, `POST /auth/patient/login`, `POST /auth/patient/resend-verification`, rate limiting (3/15m), enumeration prevention, and Alembic migrations 0007, 0008, 0009.
- **Registration Flow Integration (`test_email_registration_flow.py`)**: 2 end-to-end integration tests verifying multi-step registration lifecycle (register → resend invalidation → verify token & set password → login).
- **Login Separation Integration (`test_login_separation.py`)**: 3 integration tests verifying patient vs staff login isolation and presence of `Deprecation: true` and `Sunset` headers on legacy OTP endpoints.
- **Email Provider (`test_email_provider.py`)**: 16 tests verifying `EmailClient` initialization, console/mock/SMTP/SendGrid/SES provider interfaces, template rendering, Celery task dispatch, and `NotificationLog` audit records.
- **SchedulingEngine**: Slot validation, conflict detection, pessimistic lock behavior (`test_appointments.py`).
- **ClinicalRecordService**: AES-256-GCM encryption/decryption round-trip, KMS key caching, error handling (`test_clinical_records.py`).
- **OTP Verification Engine**: Code generation, validation, rate limiting, max attempts, delivery via WhatsApp/SMS failover (`test_otp_delivery.py`, `test_otp_delivery_fix.py`).

---

## Test Execution Summary

```bash
# Run complete backend test suite (152 tests)
python -m pytest tests/test_email_provider.py tests/test_auth.py tests/test_router_integration.py tests/test_auth_patient.py tests/test_jwt_audience.py tests/integration/test_email_registration_flow.py tests/integration/test_login_separation.py -v -o pythonpath=src/backend:.
```

| Test File | Description | Test Count | Status |
|---|---|---|---|
| `tests/test_email_provider.py` | Email Provider & Template Rendering | 16 | ✅ PASSED |
| `tests/test_auth.py` | Core Auth, User Operations & Passwords | 55 | ✅ PASSED |
| `tests/test_router_integration.py` | Router Pydantic Schemas & Routes | 16 | ✅ PASSED |
| `tests/test_auth_patient.py` | Patient Auth & Resend Unit Tests | 53 | ✅ PASSED |
| `tests/test_jwt_audience.py` | JWT Audience Claims & RoleChecker Boundaries | 7 | ✅ PASSED |
| `tests/integration/test_email_registration_flow.py` | E2E Registration Flow Tests | 2 | ✅ PASSED |
| `tests/integration/test_login_separation.py` | Login Isolation & Deprecation Tests | 3 | ✅ PASSED |
| **Total** | **Full Backend Test Suite** | **152** | **100% PASSED** |

---

## Recommendations & Next Actions

1. Proceed with AWS Infrastructure setup (Terraform IaC) for staging/production deployment (Task 5.1).
2. Configure CI/CD pipeline (GitHub Actions) for automated test execution on pull requests (Task 5.2).
3. Apply Alembic migrations 0007, 0008, 0009 on staging RDS database (Task 5.3).