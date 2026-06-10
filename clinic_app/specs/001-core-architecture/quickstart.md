# Developer Quickstart Guide: Core Architecture Setup

This guide provides steps for setting up, running, and testing the Clinic Modernization Platform (CMP) core architecture in a local environment.

## 1. Prerequisites
Ensure you have the following installed locally:
* **Python 3.12+**
* **Node.js v18+** & **npm**
* **Docker** (for running PostgreSQL and Redis locally)
* **Git**

---

## 2. Local Environment Configuration

### Backend Environment (`backend/.env`)
Create a `.env` file in the `backend/` directory:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cmp_db
REDIS_URL=redis://localhost:6379/0
AWS_DEFAULT_REGION=eu-west-1
AWS_KMS_KEY_ID=alias/cmp-test-key
USE_KMS_MOCK=true
VERIFICATION_TIMEOUT_SECONDS=15
```

### Frontend Environment (`frontend/.env`)
Create a `.env` file in the `frontend/` directory:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 3. Infrastructure Services Setup

Run PostgreSQL and Redis containers using Docker:
```bash
docker run --name cmp-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=cmp_db -p 5432:5432 -d postgres:16
docker run --name cmp-redis -p 6379:6379 -d redis:alpine
```

---

## 4. Backend Setup & Run

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Initialize virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run Alembic database migrations:
   ```bash
   alembic upgrade head
   ```
4. Start the FastAPI development server:
   ```bash
   uvicorn src.main:app --reload
   ```

---

## 5. Frontend Setup & Run

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```

---

## 6. Running Tests (Mandatory Gate)

Testing is **MANDATORY** and must pass before committing changes.

### Running Backend Tests
Execute pytest from the `backend/` directory:
```bash
pytest
```
Test suite coverage includes:
* `tests/unit/`: Encrypted column types, request schemas, validation logic.
* `tests/integration/`: Pessimistic locking queries, Celery notification failover chain, KMS envelope encryption cycles.
* `tests/contract/`: Schema conformance for OpenAPI endpoints.

### Running Frontend Tests
Execute tests from the `frontend/` directory:
```bash
npm run test        # Unit tests
npm run test:e2e    # Playwright offline caching and state sync tests
```
