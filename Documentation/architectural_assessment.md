# Clinic Modernization Platform (CMP) — Architectural Assessment

This document presents the formal architectural assessment of the Clinic Modernization Platform (CMP), analyzing its capability to fulfill the business, functional, and non-functional requirements under the constraints of the Nigeria Data Protection Regulation (NDPR), local network instability, and a 4-month MVP timeline.

---

## 1. Executive Summary

The proposed CMP architecture is of high quality, displaying a mature separation of concerns and a clear alignment with West African local infrastructure realities. By using a decoupled **Vite + React PWA** static client and a **FastAPI** backend over a **PostgreSQL** database, the architecture balances rapid development velocity with robust operational resiliency. 

The integration of application-level column encryption satisfies the strict compliance mandates of the NDPR. Explicit pessimistic locking at the database level provides atomic scheduling guarantees to prevent doctor double-booking. The pluggable notification failover strategy directly addresses cellular carrier instability in Nigeria. 

The architecture is highly recommended for implementation, subject to mitigating identified risks around KMS latency and search indexing limitations on encrypted clinical logs.

---

## 2. Architectural Impact

**Impact Level**: **High**

### Rationale
The platform acts as the core operating system for a scaling chain of healthcare clinics. A failure in scheduling conflicts affects clinical operations and revenue. Furthermore, because it stores, transmits, and processes restricted medical records (consultations, diagnoses, prescriptions) subject to NDPR legal guidelines, any architectural vulnerability carries high regulatory compliance risks, including severe financial penalties and data breaches.

---

## 3. Strengths

* **Atomic Schedule Integrity (FR-019)**: The choice of PostgreSQL row-level locks (`SELECT ... FOR UPDATE`) is the optimal approach to handle concurrent slot bookings. By executing validations within isolated database transactions, the system prevents race conditions at the data layer, eliminating double-bookings.
* **Separation of Clinical Data (NFR-008)**: Application-level AES-256-GCM encryption ensures that database administrators, backup operators, or cloud host compromised accounts cannot read patient consultation notes. Decryption is isolated to application runtime memory for users with authenticated clinical roles.
* **Low-Latency Mobile Optimization (NFR-002)**: The PWA design compiled with Vite allows the entire user interface shell to be cached locally and hosted on edge servers via Amazon CloudFront. This guarantees sub-3.0 second loading times over limited 3G/4G connections.
* **Offline Operations Continuity (NFR-004)**: Registering service workers to sync daily schedules to IndexedDB (Dexie.js) ensures that clinic workstations remain operational in read-only mode during local power or internet outages (a common operational occurrence in Nigerian branches).
* **Notification Delivery Resiliency (INT-004)**: The pluggable strategy-based `NotificationService` abstracts WhatsApp, Termii, and Infobip. This decouples the business logic from vendor-specific payload structures and guarantees that critical transactional alerts failover to SMS channels automatically during network outages.

---

## 4. Risks

| Risk ID | Title | Impact | Probability | Description & Mitigation |
|---|---|---|---|---|
| **R-001** | **KMS Latency & Availability** | Medium | Medium | **Description**: Every encryption or decryption action on patient records requires a network roundtrip to AWS KMS. If KMS experiences latency spikes or outages, clinical workflows will degrade.<br/>**Mitigation**: Implement Envelope Encryption. Generate a local Data Encryption Key (DEK), use KMS to encrypt the DEK, and cache the decrypted DEK in secure backend application memory for a short Time-To-Live (TTL) to avoid calling KMS on every row read. |
| **R-002** | **Encrypted Query Limitations** | High | Low | **Description**: Because clinical notes, diagnoses, and prescriptions are stored as AES-256-GCM ciphertext, standard SQL wildcard queries (e.g., `LIKE '%malaria%'`) are impossible. This limits doctors' ability to search past patient files by keyword.<br/>**Mitigation**: Implement a **Deterministic Blind Index**. For searchable columns like `diagnosis`, store a SHA-256 hash of the lowercase, normalized term in a separate column. The application can query matches by hashing the search input and querying the blind index. |
| **R-003** | **Clock-Drift and Outdated Cache** | Medium | Medium | **Description**: In offline mode, the PWA relies on the client device's local system clock to determine if the 2-hour read-only cache is valid. If a workstation's clock drifts, it may render expired schedules or reject updates.<br/>**Mitigation**: Implement a server-time synchronization check on startup. Compare the browser clock with the API server response time and trigger an administrative warning if the drift exceeds 30 seconds. |
| **R-004** | **Dual-Channel Notification Spam** | Low | High | **Description**: If the WhatsApp delivery confirmation webhook is delayed due to carrier latency, the Celery failover task might assume a timeout and trigger a duplicate SMS notification, confusing the patient and increasing SMS costs.<br/>**Mitigation**: Extend the timeout window to 15 seconds, and implement message deduplication states inside the `verification_otps` table to block secondary deliveries once a webhook confirmation registers. |

---

## 5. Recommendations

1. **Adopt Blind Indexing for Searchable Clinical Fields**  
   Introduce a blind index column for common lookup parameters (e.g., ICD-10 diagnosis codes). When a doctor saves a record, the backend generates `blind_index = SHA256(lowercase(diagnosis_code) + salt)`. This allows exact-match lookups without exposing plaintext fields to database administrators.
2. **Configure KMS Envelope Encryption with Memory Caching**  
   Configure the [clinical_records](file:///C:/Users/DELL/Documents/Project/clinic_app/technical_specification.md#L141-L151) service to utilize AWS KMS envelope encryption rather than direct KMS data encryption. Keep the Master Key in KMS and use it to decrypt the local Data Encryption Key (DEK), caching the DEK using a local memory cache with a maximum 5-minute TTL.
3. **Establish Strict Idempotency Keys on Booking APIs**  
   Add an `idempotency_key` (UUID) requirement on the `POST /api/v1/appointments` API. Patients booking over unstable mobile networks may double-click booking actions. The API must check Redis for active transaction keys before executing database locks.
4. **Implement Client-Side Clock Sync Protocol**  
   Include a synchronization check during the PWA's initial network handshake to align browser client times with the backend PostgreSQL database server clock, preventing cache invalidation errors.

---

## 6. Validation Plan

### 6.1 Concurrency & Scheduling Load Test
* **Objective**: Validate that pessimistic locks prevent double-booking under extreme concurrent requests.
* **Method**: Use a load-testing tool (e.g., Locust or k6) to simulate 100 concurrent users attempting to book the exact same doctor availability slot simultaneously.
* **Success Criteria**: Exactly 1 request succeeds with HTTP 201; 99 requests fail with HTTP 409 (Conflict); zero database deadlocks occur.

### 6.2 Offline Resilience Sandbox Test
* **Objective**: Validate that the workstation dashboard maintains read-only accessibility during internet disconnections.
* **Method**: Load the PWA, populate IndexedDB with mock schedule data, disconnect the local network interfaces, and verify that the UI renders the schedule and blocks write attempts with a localized offline error notification.
* **Success Criteria**: App shell renders, cached records load in < 1.0s, and booking actions are gracefully disabled.

### 6.3 Security Policy and Admin Isolation Audit
* **Objective**: Confirm that database administrators cannot read clinical records.
* **Method**: Connect to the PostgreSQL database using an administrative superuser account and execute a select query on the `clinical_records` table.
* **Success Criteria**: Plaintext notes and diagnoses return as ciphertext strings, and decrypt requests using admin IAM credentials are blocked by AWS KMS key policies.

### 6.4 Notification Gateway Timeout Failover Validation
* **Objective**: Verify that notification timeouts trigger SMS fallbacks.
* **Method**: Simulate an outage by routing WhatsApp Business API requests to a mock endpoint returning a 504 Gateway Timeout.
* **Success Criteria**: Celery task captures the timeout after 15 seconds, records the failure in `NotificationLog`, and dispatches the fallback alert via the Termii SMS adapter.

---

## 7. ADR Requirements

The current decisions are documented in:
* [ADR-001 (PostgreSQL Primary Datastore)](file:///C:/Users/DELL/Documents/Project/clinic_app/adr-001-postgresql-primary-datastore.md)
* [ADR-002 (Vite + React PWA Frontend)](file:///C:/Users/DELL/Documents/Project/clinic_app/adr-002-react-pwa-client.md)
* [ADR-003 (Application Column Encryption)](file:///C:/Users/DELL/Documents/Project/clinic_app/adr-003-application-level-column-encryption.md)
* [ADR-004 (Notification Failover Architecture)](file:///C:/Users/DELL/Documents/Project/clinic_app/adr-004-pluggable-notification-failover.md)

### Identified Future ADR Requirements
1. **ADR-005 (Payment Gateway Integration)**: To be written in Phase 2, assessing Paystack vs. Flutterwave API structures and settlement terms.
2. **ADR-006 (AI LLM Orchestration & Chatbot Engine)**: To be written in Phase 2, assessing Python-based LLM frameworks (Genkit, LangChain, or direct API integration) for the WhatsApp AI scheduling chatbot.
