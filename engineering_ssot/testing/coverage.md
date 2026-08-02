# Test Coverage Report — Clinic Modernization Platform (CMP)

**Generated**: 2026-08-02  
**Test Run**: Checkpoints 1–7 — Email-Based Patient Registration & Authentication (ADR-005) + Core Platform Test Suite  

---

## Summary

| Metric | Value |
|--------|-------|
| Total Backend Tests | 152 |
| Passed | 152 |
| Failed | 0 |
| Test Pass Rate | 100% |
| Target Coverage | 80% |

---

## Test Files Status

| Test File | Tests | Description | Status |
|-----------|-------|-------------|--------|
| `tests/test_email_provider.py` | 16 | EmailClient, Celery email tasks, NotificationLog, template rendering | ✅ PASSED |
| `tests/test_auth.py` | 55 | Core Auth, User Operations, Password policies, OTP flow | ✅ PASSED |
| `tests/test_router_integration.py` | 16 | Router Pydantic schemas & validation | ✅ PASSED |
| `tests/test_auth_patient.py` | 53 | Patient Email Registration, Verify Email, Patient Login, Resend Verification, Migrations 0007–0009 | ✅ PASSED |
| `tests/test_jwt_audience.py` | 7 | JWT `aud: "patient"` vs `aud: "staff"`, `RoleChecker` boundary enforcement | ✅ PASSED |
| `tests/integration/test_email_registration_flow.py` | 2 | End-to-end patient registration & token invalidation lifecycle | ✅ PASSED |
| `tests/integration/test_login_separation.py` | 3 | Separate patient/staff login portals & legacy OTP deprecation headers | ✅ PASSED |
| **Total** | **152** | **Full Backend Test Suite** | **100% PASSED** |

