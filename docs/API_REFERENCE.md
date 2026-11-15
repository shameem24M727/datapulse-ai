# DataPulse AI — REST & WebSocket API Reference

The DataPulse AI backend exposes RESTful endpoints and real-time WebSocket channels under `/api/v1`.

---

## 1. Authentication & Security

All protected endpoints require an `Authorization: Bearer <access_token>` header.

### 1.1 `POST /api/v1/auth/register`
Creates a new user and provisions their initial organization.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "full_name": "Jane Doe",
    "role": "data_engineer",
    "organization_name": "Primary Org"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "3f4a...",
    "token_type": "bearer",
    "expires_in": 1800
  }
  ```

### 1.2 `POST /api/v1/auth/login`
Authenticates credentials with rate-limiting brute-force lockout protection (5 failed attempts locks for 60s).
- **Request Body**: `{"email": "...", "password": "..."}`
- **Response `200 OK`**: `{"access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 1800}`

### 1.3 `POST /api/v1/auth/refresh`
Rotates refresh tokens and issues a new access token.
- **Request Body**: `{"refresh_token": "..."}`
- **Response `200 OK`**: `TokenResponse`

---

## 2. Organization Multi-Tenancy

### 2.1 `GET /api/v1/organizations/`
Lists all workspaces accessible to the caller.

### 2.2 `POST /api/v1/organizations/switch/{org_id}`
Switches active organization context and mints a new tenant-scoped access token.

---

## 3. Datasets & Data Quality

### 3.1 `POST /api/v1/datasets/upload`
Uploads a CSV or Excel file for automated schema profiling, quality score calculation, and anomaly detection.
- **Content-Type**: `multipart/form-data`
- **Response `201 Created`**: Complete dataset detail object including column profiles, deductions, and statistical outliers.

### 3.2 `GET /api/v1/datasets/`
Retrieves all uploaded datasets belonging to the active organization (cached in Redis for 120s).

### 3.3 `GET /api/v1/datasets/{id}`
Returns granular column profiling metrics, distributions, null percentages, and anomaly breakdown (cached in Redis for 300s).

---

## 4. AI Data Copilot

### 4.1 `GET /api/v1/copilot/suggestions/{dataset_id}`
Returns dynamically generated diagnostic questions tailored to the dataset's specific anomalies and quality deductions.

### 4.2 `POST /api/v1/copilot/query`
Processes user questions using Gemini API or grounded deterministic fallback engine.
- **Request Body**:
  ```json
  {
    "dataset_id": "7e629fa5-...",
    "question": "Why is the completeness score low for customer_email?"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "dataset_id": "7e629fa5-...",
    "question": "Why is the completeness score low for customer_email?",
    "answer": "The completeness score is penalized because 30 out of 100 values (30.0%) in customer_email are missing...",
    "metrics": [
      {"label": "Null Rate", "value": "30.0%"},
      {"label": "Affected Rows", "value": "30"}
    ],
    "recommendations": [
      "Implement a NOT NULL constraint at the ingestion boundary.",
      "Check upstream ETL transformation script for missing email fields."
    ]
  }
  ```

---

## 5. Streaming Pipelines & Live Telemetry

### 5.1 `POST /api/v1/pipelines/`
Registers a new streaming pipeline with a target schema.

### 5.2 `POST /api/v1/pipelines/{id}/ingest`
Ingests single or batch JSON events (up to 500 records). Validates schema, evaluates anomalies, triggers alerts on threshold breaches, and invalidates pipeline cache.

### 5.3 `GET /api/v1/pipelines/{id}/metrics`
Returns historical throughput, latency, and error snapshots (cached in Redis for 15s).

### 5.4 `POST /api/v1/pipelines/alerts/{alert_id}/acknowledge`
Marks an alert as acknowledged by an operator.

### 5.5 `POST /api/v1/pipelines/alerts/{alert_id}/resolve`
Resolves an alert and triggers automatic pipeline health recalculation.

---

## 6. Real-Time WebSockets

- **Endpoint**: `ws://localhost:8000/api/v1/pipelines/ws?token=<access_token>`
- **Handshake Authentication**: Validates JWT query token or Authorization header; binds socket session to caller's active organization.
- **Subscribed Events**:
  - `telemetry_update`: Broadcasts throughput RPS, avg latency ms, records accepted/rejected.
  - `status_change`: Broadcasts pipeline lifecycle status (`active`, `stopped`, `degraded`, `error`).
  - `alert_raised`: Emits real-time violation alerts (repeated schema violations, high failure rate, anomaly spikes).
  - `alert_updated`: Broadcasts alert acknowledgment and resolution events.
