# ADR-001: PostgreSQL as Primary Datastore

**Status**: Accepted  
**Date**: 2026-06-04  
**Deciders**: Antigravity (AI Architect), Clinic Owner, Engineering Lead

---

## Context / Problem Statement

CMP manages scheduling, availability shifts, and medical records across multiple clinic branches with hard constraints:
- FR-004: Prevent cross-branch doctor double-booking.
- FR-019: Prevent concurrent booking race conditions (pessimistic locking).
- NFR-001: Search queries <2.0s at 100 concurrent users.
- Phase 2: Requires semantic/vector search for AI scheduling chatbot (pgvector).
- INT-005: Financial billing schema must be future-proof to avoid Phase 2 rewrites.

---

## Decision

**PostgreSQL 16+** as the primary relational database, deployed as a managed instance (AWS RDS or Supabase). All access via SQLAlchemy/SQLModel ORM. Concurrent booking checks use database-level pessimistic locking (`SELECT ... FOR UPDATE`).

---

## Consequences

### Positive
- Native `SELECT ... FOR UPDATE` eliminates scheduling race conditions at DB tier.
- Full relational integrity for normalized scheduling schema (Doctor/Patient/Branch/Shift/Appointment).
- `pgvector` extension supports Phase 2 AI semantic search.
- AWS RDS provides automated backups, replication, and multi-AZ failover.
- NDPR: Supports SSL connections and column-level access privileges.

### Negative
- Schema migrations must be planned carefully (Alembic, backward-compatible).
- Active DB connection pool management required.

### Neutral
- Schema rigidity: all entities defined upfront; changes require SQL migrations.
- Pessimistic locks must be narrow and time-bound to avoid deadlocks.

---

## Rejected Alternative

**MongoDB** — Rejected because cross-collection transactional locking for FR-004/FR-019 requires fragile application-level distributed locks (e.g., Redis Redlock), introducing unacceptable complexity for a 4-month MVP.
