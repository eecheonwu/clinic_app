# C4 Level 2 — Container Diagram

**Source**: C4 Architecture Models (2026-06-04)

---

## Containers

| Container | Technology | Responsibility |
|---|---|---|
| React PWA | Vite / React / Dexie.js | SPA client; serves UI; manages local IndexedDB offline cache |
| CloudFront CDN | AWS CloudFront | Serves PWA static assets from edge locations |
| AWS API Gateway | AWS API Gateway | Routes API traffic, applies rate limits |
| FastAPI Application Server | FastAPI, Python 3.12, async | Processes requests; enforces RBAC and pessimistic locks |
| Celery Worker Instances | Celery + Python | Async background task processors (notifications, OTP delivery) |
| Redis Queue | Redis | In-memory broker for background task queuing |
| PostgreSQL Database | PostgreSQL 16+ (AWS RDS) | ACID scheduling database, audit logs, clinical records |
| AWS KMS | AWS Key Management Service | Manages master encryption keys for clinical data |
| WhatsApp Business Cloud API | External | Transactional WhatsApp message delivery |
| Termii Gateway API | External | Primary Nigerian SMS delivery (DND-bypass) |
| Infobip Gateway API | External | Secondary/fallback SMS delivery |

---

## Dependency Flow

```
[Patient Browser / Staff Workstation]
        ↓ HTTPS / TLS 1.3
[CloudFront CDN] ──→ [React PWA (browser)]
        ↓ HTTPS API requests
[AWS API Gateway]
        ↓
[FastAPI Application Server]
    ├──→ [PostgreSQL] (reads/writes/pessimistic locks)
    ├──→ [AWS KMS] (encrypt/decrypt clinical records)
    └──→ [Redis Queue]
              ↓
        [Celery Workers]
            ├──→ [WhatsApp API] (primary)
            ├──→ [Termii API] (SMS failover)
            └──→ [Infobip API] (SMS backup)
```

---

## Container Diagram (Mermaid)

```mermaid
graph TB
    subgraph ClientTier ["Client Tier - Browser"]
        PWA["React PWA Container\nSingle Page App - Vite / React / Dexie.js\nServes UI, handles local IndexedDB cache"]
    end

    subgraph EdgeTier ["Edge Tier - AWS Infrastructure"]
        CDN["CloudFront CDN\nServes PWA static assets"]
        Gateway["AWS API Gateway\nRoutes API traffic, applies rate-limits"]
    end

    subgraph AppTier ["Backend Application Tier"]
        FastAPI["FastAPI Application Server\nAsync Python 3.12 REST API\nProcesses requests, enforces RBAC & locks"]
        Workers["Celery Worker Instances\nAsync task processors"]
        Redis["Redis Queue\nIn-memory broker for background tasks"]
    end

    subgraph DataTier ["Storage & Encryption Tier"]
        PostgreSQL[("PostgreSQL Database\nACID scheduling database & audit log")]
        KMS["AWS KMS\nManages Master Keys"]
    end

    subgraph External ["External Integration API Tier"]
        WhatsAppAPI["WhatsApp Business Cloud API"]
        TermiiAPI["Termii Gateway API"]
        InfobipAPI["Infobip Gateway API"]
    end

    PWA -->|Downloads static shell| CDN
    PWA -->|HTTPS API Requests / TLS 1.3| Gateway
    Gateway -->|Forwards requests| FastAPI

    FastAPI -->|Reads/Writes/Transaction Locks| PostgreSQL
    FastAPI -->|Requests Encryption/Decryption| KMS
    FastAPI -->|Publishes async events| Redis
    Redis -->|Feeds tasks| Workers

    Workers -->|Sends templates| WhatsAppAPI
    Workers -->|Sends local SMS| TermiiAPI
    Workers -->|Sends failover SMS| InfobipAPI
```
