# UML Component Diagrams

## FastAPI Backend Architecture

Decomposes the logical architecture of the **FastAPI Container** based on the Level 3 Component Diagram of the [C4 Components](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/C4/components.md) and design choices in [ADR-003](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/ADR/ADR-003-application-level-column-encryption.md) and [ADR-004](file:///C:/Users/DELL/Documents/Project/cmp/knowledge/architecture/ADR/ADR-004-pluggable-notification-failover.md).

```mermaid
graph TB
    subgraph Client [Client Tier]
        PWA[React PWA Client]
    end

    subgraph API [FastAPI Backend Container]
        subgraph Routers [API Route Controllers]
            AuthRouter[Auth & Verification Router]
            BookingRouter[Appointment Booking Router]
            ClinicalRouter[Clinical Records Router]
            ReportRouter[Operational Reports Router]
        end

        subgraph Services [Business Logic & Services]
            AuthService[Authentication & RBAC Manager]
            Scheduler[Scheduling Engine]
            ClinicalService[Clinical Record Service]
            OTPService[OTP Verification Engine]
            NotificationService[Pluggable Notification Service]
        end

        subgraph Security [Security & Cryptography]
            KMSEngryptor[KMS Envelope Encryptor]
        end
    end

    subgraph Database [Storage & Queue Tier]
        PostgreSQL[(PostgreSQL DB)]
        RedisQueue[Redis Task Queue]
    end

    subgraph External [External Services]
        AWSKMS[AWS KMS]
        WhatsAppAPI[WhatsApp Business Cloud API]
        TermiiAPI[Termii Gateway API]
        InfobipAPI[Infobip Gateway API]
    end

    PWA -->|HTTPS REST API Requests| Routers

    AuthRouter --> AuthService
    AuthRouter --> OTPService
    BookingRouter --> Scheduler
    BookingRouter --> NotificationService
    ClinicalRouter --> ClinicalService
    ClinicalRouter --> AuthService
    ReportRouter --> AuthService

    Scheduler -->|Pessimistic Row-level Locks| PostgreSQL
    ClinicalService -->|Read/Write Encrypted Columns| PostgreSQL
    ClinicalService --> KMSEngryptor
    KMSEngryptor -->|GenerateDEK / Decrypt| AWSKMS
    OTPService -->|Manage OTP sessions| PostgreSQL
    NotificationService -->|Push tasks| RedisQueue

    subgraph Background [Background Processing]
        Workers[Celery Background Workers]
    end

    RedisQueue --> Workers
    Workers --> WhatsAppAPI
    Workers --> TermiiAPI
    Workers --> InfobipAPI
```
