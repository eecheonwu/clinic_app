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
