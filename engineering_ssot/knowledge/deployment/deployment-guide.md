# Deployment Guide

**Last Updated**: 2026-07-30  
**Status**: Local Development Ready | AWS Deployment NOT STARTED

---

## Current State

### Local Development Environment

The project currently runs entirely on Docker for local development. No AWS infrastructure has been provisioned.

#### Docker Compose Services

| Service | Image | Port | Purpose |
| --------- | ------- | ------ | --------- |
| `db` | PostgreSQL 15-alpine | 5432 | Primary database (CMP database) |
| `redis` | Redis 7-alpine | 6379 | Celery broker + rate limiting |
| `backend` | Python 3.11 (built) | 8000 | FastAPI application |
| `worker` | Python 3.11 (built) | — | Celery worker for async tasks |
| `frontend` | Node 18 (built) | 5173 | Vite dev server (React PWA) |
| `localstack` | LocalStack | 4566 | AWS KMS emulation for local dev |

#### Docker Files

- `docker-compose.yml` — Local development orchestration
- `docker-compose.prod.yml` — Production configuration (not yet deployed)
- `.env.docker` — Docker environment variables
- `.dockerignore` — Docker build exclusions
- `DOCKER-README.md` — Docker setup instructions

#### LocalStack Setup

- `localstack-setup/init-kms.sh` — Initializes a KMS key in LocalStack for local encryption testing
- Used by the backend for AES-256-GCM column encryption (ADR-003)

### Start Commands

- `start-dev.bat` — Windows start script
- `start-dev.sh` — Linux/Mac start script
- `Makefile` — Make targets for common operations

---

## Planned AWS Deployment (NOT YET IMPLEMENTED)

Per the implementation plan (Tasks 5.1–5.4), the following AWS infrastructure is planned but has NOT been created:

### Target Architecture

| Component | AWS Service | Purpose |
| ----------- | ------------- | --------- |
| Database | RDS PostgreSQL 15 | Primary datastore (ADR-001) |
| Cache | ElastiCache Redis 7 | Celery broker + rate limiting |
| Frontend | S3 + CloudFront | Static PWA hosting (ADR-002) |
| API | API Gateway + ECS Fargate | Backend API hosting |
| Secrets | Secrets Manager | Database credentials, API keys |
| Encryption | KMS | Column encryption key management (ADR-003) |
| Notifications | WhatsApp Business API, Termii, Infobip | OTP delivery (ADR-004) |
| Monitoring | CloudWatch | Logs, metrics, alarms |

### Deployment Tasks Status

| Task | Description | Status |
| ------ | ------------- | -------- |
| Task 5.1 | Infrastructure Setup (Terraform IaC) | ❌ NOT STARTED |
| Task 5.2 | CI/CD Pipeline (GitHub Actions) | ❌ NOT STARTED |
| Task 5.3 | Staging Environment & Rollout | ❌ NOT STARTED |
| Task 5.4 | Monitoring & Alerting Setup | ❌ NOT STARTED |

### Missing Infrastructure Artifacts

- No Terraform files (`infra/` directory does not exist)
- No GitHub Actions workflows (`.github/workflows/` does not exist)
- No CloudFormation templates
- No AWS deployment scripts

---

## Database Migration Strategy

### Alembic Configuration

- `alembic.ini` — Alembic configuration
- `alembic/env.py` — Environment setup
- `alembic/versions/` — Migration scripts (6 migrations: 0001–0006)
- `init-db/init.sql` — Initial database initialization

### Migration Commands

    # Apply all migrations
    alembic upgrade head

    # Rollback one migration
    alembic downgrade -1

    # Check current revision
    alembic current

### Current Migrations

| Migration | Description | Date |
| ----------- | ------------- | ------ |
| 0001 | Initial schema (users, branches) | 2026-07-07 |
| 0002 | OTP verification | 2026-07-07 |
| 0003 | Notifications log | 2026-07-08 |
| 0004 | Doctor availability, appointments | 2026-07-08 |
| 0005 | Clinical records | 2026-07-09 |
| 0006 | Security audit logs | 2026-07-10 |

---

## Environment Configuration

### Required Environment Variables

| Variable | Purpose | Local Default |
| ---------- | --------- | --------------- |
| `DATABASE_URL` | PostgreSQL connection | `postgresql://cmp:cmp@db:5432/cmp` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | JWT signing | Dev key in .env.docker |
| `KMS_KEY_ID` | AWS KMS key for encryption | LocalStack key |
| `AWS_ACCESS_KEY_ID` | AWS credentials | LocalStack test key |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | LocalStack test key |
| `AWS_ENDPOINT_URL` | LocalStack endpoint | `http://localstack:4566` |
| `WHATSAPP_TOKEN` | WhatsApp Business API | Test token |
| `TERMII_API_KEY` | Termii SMS API | Test key |
| `INFOBIP_API_KEY` | Infobip SMS API | Test key |

---

## Future: Email-based Patient Registration Deployment

When the Email-based Patient Registration feature (ADR-005) is implemented, the following additional deployment configuration will be needed:

- Email provider settings (SMTP/SendGrid/AWS SES)
- DKIM/SPF/DMARC DNS records
- `EMAIL_VERIFICATION_BASE_URL` environment variable
- `EMAIL_FROM_ADDRESS` and `EMAIL_FROM_NAME` configuration
- CloudWatch alarms for email delivery failure rate > 5%

---

## References

- `docker-compose.yml` — Local development
- `docker-compose.prod.yml` — Production configuration
- `DOCKER-README.md` — Docker setup guide
- `alembic.ini` — Migration configuration
- `knowledge/architecture/ADR/ADR-001-postgresql-primary-datastore.md`
- `knowledge/architecture/ADR/ADR-002-react-pwa-client.md`
- `knowledge/architecture/ADR/ADR-003-application-level-column-encryption.md`
- `knowledge/architecture/ADR/ADR-004-pluggable-notification-failover.md`
- `knowledge/engineering/implementation-plan.md` — Tasks 5.1–5.4
