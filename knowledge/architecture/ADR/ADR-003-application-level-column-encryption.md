# ADR-003: Application-Level Column Encryption for Clinical Records

**Status**: Accepted  
**Date**: 2026-06-04  
**Deciders**: Antigravity (AI Architect), Clinic Owner, Security Officer

---

## Context / Problem Statement

CMP stores highly sensitive patient medical records with strict regulatory requirements:
- NFR-005: NDPR compliance.
- NFR-006: Clinical notes/histories/diagnoses encrypted at rest (AES-256) and in transit (TLS 1.3).
- NFR-008: System administrators MUST NOT be able to read patient clinical records, consultation notes, or diagnostic files.

---

## Decision

**Application-Level Column Encryption** using **AES-256-GCM** for all restricted medical fields (`notes`, `diagnosis`, `prescriptions`). FastAPI backend encrypts before DB write; decrypts only for authenticated clinical-role users. Encryption keys managed and rotated via **AWS KMS** with IAM policies scoped strictly to the backend application server's IAM role.

**Envelope encryption**: A local Data Encryption Key (DEK) encrypted by the KMS Master Key is cached in application memory to minimize KMS API roundtrip latency.

**Probabilistic encryption**: Random IV per write prevents pattern analysis from repeated plaintexts.

---

## Consequences

### Positive
- Absolute compliance with NFR-008: DB admins and cloud hosts see only ciphertext.
- AES-256-GCM provides both confidentiality and integrity verification (authenticated encryption — tamper-resistant).
- AWS KMS provides auditable access logging and automated key rotation.

### Negative
- Encrypted columns cannot be SQL-searched (no `LIKE '%diabetes%'` queries on clinical notes).
- Slight performance overhead per API request (mitigated by DEK caching / envelope encryption).

### Neutral
- Search on clinical data must use unencrypted metadata (tags, date ranges, codes) or client-side search after decryption.
- KMS misconfiguration or key compromise blocks all clinical access globally — requires key backup and rotation policies.

---

## Rejected Alternative

**Database Transparent Data Encryption (TDE)** — Rejected because TDE decrypts transparently for all DB users, meaning any database administrator or compromised DB connection can query patient clinical notes in plaintext. Fails NFR-008 entirely.
