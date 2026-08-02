# CMP — Product Requirements

**Source**: SRD v1.3 (Approved, 2026-06-04)

---

## Vision & Mission

Transition a chain of 3 (→15) private healthcare clinics from manual paper/WhatsApp workflows to a secure, cloud-hosted digital operations platform, reducing no-shows, eliminating scheduling conflicts, and ensuring NDPR-compliant patient data management.

---

## Business Goals

| ID | Goal | Target |
|---|---|---|
| BG-001 | Reduce receptionist manual scheduling time | −70% within 6 months |
| BG-002 | Reduce patient appointment no-show rates | −25–30% within 6 months |
| BG-003 | Digitise 100% of new patient registration & consultation records | All active branches |
| BG-004 | Eliminate schedule conflicts and double-bookings for all doctors | All branches |
| BG-005 | Provide real-time consolidated operational dashboards | Eliminate manual reports |

---

## Actors / Personas

| Role | Interaction |
|---|---|
| Patient | Mobile responsive portal — books, reschedules, cancels |
| Receptionist | Desktop UI — check-in, walk-in registration, phone bookings |
| Doctor | Tablet/Desktop — clinical notes, consultation logs, daily schedule |
| Branch Manager | Laptop — single-branch operational dashboard |
| Senior Manager | Laptop — cross-clinic aggregated metrics |
| System Administrator | Admin console — branches, roles, settings |
| WhatsApp Gateway | REST API/Webhook — outbound transactional messages |
| SMS Gateway (Termii/Infobip) | REST API — outbound failover SMS |

---

## Functional Requirements

### Authentication & RBAC
| ID | Description | Priority |
|---|---|---|
| FR-001 | Patient self-registration with phone/email/password + OTP verification | Must |
| FR-002 | Role-Based Access Control (Patient, Receptionist, Doctor, Manager, Admin, Executive) | Must |

### Scheduling & Appointment Engine
| ID | Description | Priority |
|---|---|---|
| FR-003 | Appointment booking by patients and receptionists | Must |
| FR-004 | Cross-branch doctor schedule conflict check (no double-booking) | Must |
| FR-005 | Rescheduling & cancellation up to 2 hours before appointment | Must |
| FR-012 | Progressive cancellation warning logged for <2h cancellations (Tier 1) | Must |
| FR-013 | Soft Flag on profile for 2–3 late cancellations/no-shows in 90 days (Tier 2) | Must |
| FR-014 | Block self-service booking for ≥4 late cancellations/no-shows in 90 days (Tier 3) | Must |
| FR-015 | Staff override of patient booking restrictions | Must |
| FR-016 | Emergency cancellation exemption (no penalty) | Must |
| FR-017 | Clinic-initiated cancellation — no patient penalty | Must |
| FR-018 | Time-bound doctor availability blocks per branch | Must |
| FR-019 | Server-side booking validation with pessimistic DB locks (race condition prevention) | Must |
| FR-020 | Emergency schedule override by Admins/Managers with audit log | Must |
| FR-021 | Auto-flag affected appointments and notify on doctor shift cancellation | Must |

### Clinical Records
| ID | Description | Priority |
|---|---|---|
| FR-006 | Doctor records consultation notes, diagnoses, prescriptions; notes encrypted | Must |
| FR-007 | Emergency cross-branch patient record access (with audit log) | Must |
| FR-008 | Lab results hidden from patient until doctor marks "Released" | Must |

### Front Desk
| ID | Description | Priority |
|---|---|---|
| FR-009 | Receptionist walk-in registration and immediate slot booking | Must |
| FR-010 | Patient check-in by receptionist; doctor dashboard notified | Must |

### Management
| ID | Description | Priority |
|---|---|---|
| FR-011 | Real-time branch operational reports for Managers/Senior Management | Must |

---

## Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-001 | Performance | Patient/doctor search queries < 2.0s at 100 concurrent users |
| NFR-002 | Performance | Key page loads < 3.0s on Nigerian 3G/4G |
| NFR-003 | Availability | ≥99.9% uptime Mon–Sat 07:00–20:00 WAT |
| NFR-004 | Offline Resiliency | Browser caches current-day appointments for ≥2h read-only offline access |
| NFR-005 | Security/NDPR | Full NDPR compliance for all patient data storage/processing |
| NFR-006 | Security | Clinical notes/histories/diagnoses encrypted at rest (AES-256) & in transit (TLS 1.3) |
| NFR-007 | Security | Immutable audit log for every read/write/modification of patient records |
| NFR-008 | Security | System admins CANNOT read patient clinical records or consultation notes |

---

## Integration Requirements

| ID | System | Type | Direction | Requirement |
|---|---|---|---|---|
| INT-001 | WhatsApp Business Cloud API | REST | Outbound | Booking confirmations, change alerts, 24h & 2h reminders |
| INT-002 | Termii Gateway | REST | Outbound | Primary Nigerian SMS (DND-bypass) |
| INT-003 | Infobip Gateway | REST | Outbound | Secondary fallback SMS |
| INT-004 | NotificationService Abstraction | Internal | — | Pluggable layer: no vendor lock-in, auto-failover |
| INT-005 | Paystack/Flutterwave (Phase 2) | Webhook/REST | Bi-directional | DB schema includes payment states; no Phase 1 transaction routing |

---

## AI Requirements (Phase 2)

| ID | Requirement | Priority |
|---|---|---|
| AI-001 | Chatbot refuses medical diagnosis questions with disclaimer | High (Phase 2) |
| AI-002 | Fallback to rule-based menu on LLM timeout (>5s) | High (Phase 2) |
| AI-003 | Chatbot transparently identifies itself as automated | High (Phase 2) |
| AI-004 | Hand-off to human receptionist after 3 failed turns | High (Phase 2) |

---

## Constraints

| Type | Constraint |
|---|---|
| Timeline | MVP Phase 1 deployed within 4 months of kick-off |
| Budget | Cost-effective cloud (AWS preferred) |
| Platform | Public cloud only; responsive web (no native apps) |
| Regulatory | NDPR compliance mandatory |
| Technology | No on-premise servers |

---

## Business Rules

- Doctors cannot be double-booked across branches at overlapping times (FR-004).
- Late cancellation (<2h) triggers tiered penalty progression (FR-012–FR-014).
- Clinical records are encrypted; only Doctors can decrypt via KMS-scoped IAM (NFR-008).
- Immutable audit log written within same DB transaction as any clinical record change (NFR-007).
- Medical records retained for minimum 10 years (DR-002).
- DB schema includes payment states (pending/deposit_paid/fully_paid/waived/refunded) to avoid Phase 2 schema rewrites (INT-005).

---

## Data Classification

| Class | Data |
|---|---|
| Confidential | Patient profile details, phone numbers, email addresses |
| Restricted (Medical) | Consultation logs, diagnostic images, prescriptions, diagnoses |
| Internal | Operational performance reports, branch utilization metrics |

---

## Open Questions

None. All elicitation open questions resolved (OQ-001).
