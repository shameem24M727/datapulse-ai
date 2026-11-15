# DataPulse AI — Complete Installation & Setup Guide

This guide covers local environment setup, configuration, database migrations, running the application, and containerized deployment.

---

## 1. Prerequisites

Ensure the following tools are installed:
- **Node.js**: v18+ (v20+ recommended) and `npm`
- **Python**: 3.10+ (tested on Python 3.10, 3.11, 3.12)
- **PostgreSQL**: v14+ (optional — automatically falls back to SQLite if PostgreSQL is unavailable)
- **Redis**: v7+ (optional — automatically falls back to direct database queries if Redis is offline)

---

## 2. Repository Setup

```bash
git clone https://github.com/your-username/DataPulse-AI.git
cd DataPulse-AI
```

---

## 3. Backend Setup

### 3.1 Create Virtual Environment & Install Dependencies
```bash
cd backend
python -m venv venv

# On Linux / macOS:
source venv/bin/activate

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2 Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

Key environment settings:
```env
# Application
APP_NAME="DataPulse AI"
DEBUG=False

# Primary Database
DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/datapulse_ai"
SQLITE_FALLBACK_URL="sqlite:///./datapulse.db"

# Security & JWT Tokens (Must change in production)
JWT_SECRET_KEY="generate-a-secure-random-32-byte-secret-here"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google Gemini AI Studio Key (Optional: Falls back to deterministic engine)
GEMINI_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-2.5-flash"

# Redis In-Memory Cache (Optional: Falls back to direct DB)
REDIS_ENABLED=true
REDIS_URL="redis://localhost:6379/0"
REDIS_TIMEOUT_SECONDS=1.0
REDIS_KEY_PREFIX="datapulse"
```

### 3.3 Apply Database Migrations
```bash
alembic upgrade head
```

### 3.4 Start Backend Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Base: `http://localhost:8000`
- Swagger Interactive Documentation: `http://localhost:8000/api/docs`
- Health Diagnostics: `http://localhost:8000/api/v1/health/detailed`

---

## 4. Frontend Setup

### 4.1 Install Packages
```bash
cd ../frontend
npm install
```

### 4.2 Start Development Server
```bash
npm run dev
```
Open **http://localhost:5173** in your browser.

### 4.3 Build for Production
```bash
npm run build
```
Production assets are generated in `frontend/dist/`.

---

## 5. Running with Docker & Compose

For a complete containerized stack (PostgreSQL + Redis + FastAPI Backend + React Frontend):

```yaml
# docker-compose.yml example
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: datapulse_ai
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    environment:
      DATABASE_URL: "postgresql+psycopg2://postgres:password@postgres:5432/datapulse_ai"
      REDIS_URL: "redis://redis:6379/0"
      JWT_SECRET_KEY: "prod-secret-key-replace-with-secure-value"
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

Launch with:
```bash
docker-compose up -d
```

---

## 6. Running Automated Tests

```bash
cd backend
$env:PYTHONPATH='backend'; python -m unittest discover tests -v
```
All 86 tests verify data ingestion, quality scoring, statistical anomaly detection, streaming pipelines, WebSockets, RBAC multi-tenancy, Redis caching, and end-to-end user workflows.
