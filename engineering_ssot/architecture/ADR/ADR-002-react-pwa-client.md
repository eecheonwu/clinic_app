# ADR-002: Vite + React PWA (SPA) for Frontend

**Status**: Accepted  
**Date**: 2026-06-04  
**Deciders**: Antigravity (AI Architect), Clinic Owner, Frontend Lead

---

## Context / Problem Statement

CMP frontend must:
- Load <3.0s on Nigerian 3G/4G (NFR-002, UG-001).
- Support receptionist/doctor desktops and patient mobile (UG-002, UG-003).
- Provide ≥2h read-only offline access to current-day appointment lists during internet outages (NFR-004).
- Deploy within 4-month timeline on cost-effective cloud hosting.

---

## Decision

**Vite + React SPA** packaged as a Progressive Web App (PWA). Offline caching via **Workbox** (Service Worker) + **Dexie.js** (IndexedDB wrapper). Deployed as static build to **AWS S3 + Amazon CloudFront CDN**.

---

## Consequences

### Positive
- Static hosting on S3/CloudFront: near-zero infrastructure cost, sub-second asset delivery via CDN edge.
- Full Service Worker lifecycle control: clean implementation of NFR-004 offline cache.
- High development speed; decoupled from backend API evolution.

### Negative
- Client-side routing requires loading states on first load.
- State synchronization scripts needed: client fetches schedules daily to IndexedDB; shows "Offline Mode — Read Only" banner on network loss.

### Neutral
- SEO low — irrelevant, all features behind authentication.
- CORS configuration required on FastAPI backend for CDN domain.
- Sensitive IndexedDB data must be purged on logout/session expiry (security requirement).

---

## Rejected Alternative

**Next.js (App Router/SSR)** — Rejected because SSR requires Node.js server infrastructure (cost + complexity) and is fundamentally incompatible with the offline PWA Service Worker requirement (NFR-004) when server components cannot execute during network disconnection.
