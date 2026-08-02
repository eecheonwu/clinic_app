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
| 0007 | Email verification tokens table (`email_verification_tokens`) | 2026-08-02 |
| 0008 | User email verification flags (`is_email_verified`, `email_verified_at`) | 2026-08-02 |
| 0009 | Email NOT NULL constraint in `users` (`users.email NOT NULL`) | 2026-08-02 |

#### Migration Deployment Verification Procedure
1. **Staging Upgrade**: Execute `alembic upgrade head` in staging.
2. **Schema & Data Verification**: Verify `email_verification_tokens` table exists, `users.email` is `NOT NULL`, and no data loss occurred.
3. **Downgrade Testing**: Execute `alembic downgrade 0006` to verify reversible migration scripts.
4. **Final Upgrade**: Re-apply `alembic upgrade head`.

---

## Email Infrastructure & Security Configuration (ADR-004 & ADR-005)

### Email Provider Environment Settings

| Variable | Purpose | Staging/Prod Source |
| ---------- | --------- | -------------------- |
| `EMAIL_PROVIDER` | Active provider (`console`, `smtp`, `sendgrid`, `ses`) | AWS Secrets Manager / Parameter Store |
| `EMAIL_FROM_ADDRESS` | Sender address (`noreply@clinic.ng`) | Environment Config |
| `EMAIL_FROM_NAME` | Sender display name (`Clinic Modernization Platform`) | Environment Config |
| `EMAIL_VERIFICATION_BASE_URL` | Patient password setup URL (`https://patient.clinic.ng/patient/create-password`) | Environment Config |
| `SENDGRID_API_KEY` | API Key for SendGrid provider | AWS Secrets Manager (`/cmp/prod/sendgrid_api_key`) |
| `AWS_SES_REGION` | AWS region for SES provider (`af-south-1`) | Environment Config |
| `AWS_SES_ACCESS_KEY_ID` | IAM credentials for SES | AWS Secrets Manager (`/cmp/prod/aws_ses`) |
| `AWS_SES_SECRET_ACCESS_KEY` | IAM credentials for SES | AWS Secrets Manager (`/cmp/prod/aws_ses`) |
| `SMTP_HOST` / `SMTP_PORT` | SMTP fallback server host & port | Environment Config |
| `SMTP_USER` / `SMTP_PASSWORD` | SMTP authentication credentials | AWS Secrets Manager (`/cmp/prod/smtp`) |

### AWS Secrets Manager Integration

Secrets are fetched at runtime or injected into container environment variables via AWS ECS task definitions:
- Secret Name: `cmp/production/secrets`
  - `SENDGRID_API_KEY`
  - `SMTP_PASSWORD`
  - `AWS_SES_SECRET_ACCESS_KEY`
  - `JWT_SECRET_KEY`

### DNS Deliverability & Authentication (SPF, DKIM, DMARC)

To prevent spoofing and ensure high inbox placement for email verification links:

1. **SPF Record (TXT)**:
   `v=spf1 include:sendgrid.net include:amazonses.com ~all`
2. **DKIM Record (CNAME)**:
   Configured via SendGrid / AWS SES CNAME tokens pointing to domain key verifiers.
3. **DMARC Record (TXT)**:
   `_dmarc.clinic.ng` TXT record: `v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc-reports@clinic.ng;`

---

## Email Delivery Monitoring & Alerting (Task 11)

### CloudWatch Monitoring & Metrics

1. **NotificationLog Tracking**:
   All email delivery attempts (registration tokens, resend requests) log entries in `notification_logs` with channel `email`, provider name (`console`/`smtp`/`sendgrid`/`ses`), status (`SENT`/`FAILED`), and latency.
2. **CloudWatch Custom Metric**: `CMP/Notifications` -> `EmailDeliveryFailures` & `EmailDeliverySuccesses`.
3. **CloudWatch Alarm Configuration**:
   - **Alarm Name**: `CMP-HighEmailDeliveryFailureRate`
   - **Metric**: `EmailDeliveryFailures / (EmailDeliveryFailures + EmailDeliverySuccesses) * 100`
   - **Threshold**: `> 5%` over a 5-minute evaluation period.
   - **Action**: Trigger SNS notification to DevOps on-call queue and fallback to backup provider per ADR-004.

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
- `knowledge/architecture/ADR/ADR-005-email-patient-registration.md`
- `knowledge/engineering/task-plan.md` — Checkpoints 1–7

