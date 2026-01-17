# Classifier Service

**Port:** `8003`  
**Base URL:** `http://localhost:8003`  
**Service Name:** `classifier-service`

The Classifier Service provides email classification functionality. It implements a two-stage classification pipeline: high recall (loose filter) and high precision (strict classification).

---

## Endpoints

### Health Check

#### `GET /health`

Returns the health status of the Classifier Service.

**Authentication:** None

**Response:**
```json
{
  "status": "ok",
  "service": "classifier-service",
  "timestamp": "2026-01-17T19:57:10Z",
  "uptime_seconds": 8.39
}
```

**Example:**
```bash
curl http://localhost:8003/health
```

---

### Root

#### `GET /`

Returns service information.

**Authentication:** None

**Response:**
```json
{
  "service": "classifier-service",
  "docs": "/docs"
}
```

**Example:**
```bash
curl http://localhost:8003/
```

---

## Classification Pipeline

The Classifier Service implements a two-stage classification pipeline:

### Stage 1: High Recall (Loose Filter)

**Goal:** Do not miss job emails.

**Signals:**
- Subject keywords (e.g., "application", "interview", "thank you for applying")
- Known ATS senders (Greenhouse, Lever, Workday, etc.)
- Common phrases: "Thank you for applying", "Interview", "Application update"

**Result:** `candidate_job_emails[]` - List of emails that might be job-related.

---

### Stage 2: High Precision (Strict Classification)

**Input:** `candidate_job_emails[]` from Stage 1.

**Output:** Exactly ONE of:
- `applied` - Application confirmation
- `rejected` - Rejection email
- `interview` - Interview invitation/scheduling
- `offer` - Offer letter or acceptance
- `ghosted` - (Handled externally by time-based logic)
- `skip` - Uncertain or not job-related

**Rules:**
- If uncertain → `skip` (but counted).
- Never assign multiple categories.
- Never invent categories.

---

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | No | - |

---

## Notes

- Currently a base service (Step 3). Full classification logic will be implemented in Step 6.
- The service is called by the gmail-connector service for email classification.
- Classification happens during Gmail sync.
- Ghosted detection is handled by the gmail-connector service (time-based logic).

---

## Future Endpoints (Step 6)

The following endpoints will be added in Step 6:

- `POST /classify` - Classify a single email
- `POST /classify/batch` - Classify multiple emails
- `GET /classifier/stats` - Classification statistics

---

## Error Responses

All endpoints may return standard error responses:

```json
{
  "detail": "Error message here"
}
```

**Common Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Invalid request
- `500 Internal Server Error` - Server error
