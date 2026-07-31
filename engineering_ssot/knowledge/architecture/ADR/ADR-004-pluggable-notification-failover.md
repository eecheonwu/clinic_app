# ADR-004: Pluggable Notification Service with Multi-Provider Failover

**Status**: Accepted  
**Date**: 2026-06-04  
**Deciders**: Antigravity (AI Architect), Clinic Owner, Integration Engineer

---

## Context / Problem Statement

CMP relies on notifications for BG-002 (reduce no-shows 25–30%). Nigeria's mobile network carrier routing is unstable; DND policies block transactional SMS unless routed through licensed domestic gateways (DND-bypass). Requirements:
- INT-001: WhatsApp Business Cloud API integration.
- INT-002: Termii as primary Nigerian SMS (DND-bypass for MTN/Airtel/Glo/9mobile).
- INT-003: Infobip as secondary SMS fallback.
- INT-004: Pluggable `NotificationService` abstraction — no vendor lock-in, auto-failover.

---

## Decision

**Pluggable Notification Abstraction Layer** using the **Strategy Pattern**. A generic `NotificationService` interface is defined. Concrete adapter classes implement it per vendor (`WhatsAppCloudAPIClient`, `TermiiSMSClient`, `InfobipSMSClient`). Delivery is routed via async worker queue (Celery + Redis) with the following failover chain:

1. **WhatsApp Business Cloud API** (primary — cheaper, rich media)
2. **Termii SMS** (secondary — DND-bypass for Nigerian carriers)
3. **Infobip SMS** (tertiary backup)

---

## Consequences

### Positive
- No vendor lock-in (INT-004): new providers are added by implementing the interface.
- Maximum delivery reliability: patients receive reminders even if primary gateway goes offline.
- Async worker execution: notification latency does not block booking confirmation HTTP responses.

### Negative
- Three provider integrations to maintain and test.
- Risk of duplicate messages on false-positive timeout failovers — mitigated by idempotency tracking in `NotificationLog`.

### Neutral
- Requires async queue infrastructure (Redis + Celery).
- Requires `NotificationLog` DB table (attempts, provider, status, error codes) for billing audits and failover optimization.
- Cost hierarchy: WhatsApp (cheapest/preferred) → Termii → Infobip.

---

## Rejected Alternative

**Single Notification Provider (e.g., Infobip Only)** — Rejected. Single point of failure; global providers less reliable at Nigerian DND-bypass. Does not satisfy INT-002 or INT-004.

---

## Implementation Details (2026-07-12)

### OTP Delivery Flow

The OTP delivery system was implemented with the following components:

1. **auth_service.create_otp()** - Modified to return tuple `(VerificationOTP, str)` containing both the OTP record and the plain text OTP code for delivery.

2. **verify_request() endpoint** - Enqueues Celery task for async OTP delivery with sync fallback:
   ```python
   try:
       if CELERY_AVAILABLE:
           send_otp_task.delay(str(otp.id), otp_code)
       else:
           # Fallback: send synchronously
           orchestrator = NotificationOrchestrator(db)
           success, error, provider = await orchestrator.send_otp(
               otp.phone_number, otp_code
           )
   except Exception:
       # Don't fail request if notification fails
       pass
   ```

3. **send_otp_task** - Celery task that accepts `otp_code` parameter and delivers via the failover chain.

### Security Considerations

- OTPs are hashed using bcrypt before database storage
- Plain text OTP is only used during delivery and never persisted
- Rate limiting: 3 requests per 15 minutes per phone number
- Max attempts: 5 verification attempts before OTP expires
- 10-minute TTL for OTP validity
- Idempotency prevents duplicate notification sends

### Test Coverage

- 13 tests in `tests/test_otp_delivery.py` covering:
  - OTP generation (length, uniqueness)
  - OTP hashing and verification
  - Rate limiting enforcement
  - Notification delivery via WhatsApp
  - Fallback to SMS providers
  - Complete OTP flow integration

---

## Files Modified

1. `src/backend/services/auth_service.py` - Modified `create_otp()` to return tuple
2. `src/backend/api/v1/auth/router.py` - Implemented OTP delivery in `verify_request()`
3. `src/backend/workers/tasks.py` - Updated `send_otp_task` to use actual OTP code
4. `tests/test_otp_delivery.py` - New comprehensive test suite