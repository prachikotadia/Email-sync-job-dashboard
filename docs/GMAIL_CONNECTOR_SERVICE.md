# Gmail Connector Service

**Port:** `8002`  
**Base URL:** `http://localhost:8002`  
**Service Name:** `gmail-connector`

The Gmail Connector Service handles Gmail synchronization, email fetching, classification, and application tracking. It fetches ALL emails from Gmail (no limits) and stores them in the database.

---

## Endpoints

### Health Check

#### `GET /health`

Returns the health status of the Gmail Connector Service and its dependencies.

**Authentication:** None

**Response:**
```json
{
  "status": "ok" | "degraded",
  "service": "gmail-connector",
  "timestamp": "2026-01-17T19:57:10Z",
  "uptime_seconds": 8.11,
  "database": {
    "status": "ok" | "error",
    "message": "Error message if status is error"
  },
  "classifier_service": {
    "status": "ok" | "error",
    "status_code": 200,
    "message": "Error message if status is error"
  },
  "active_sync_jobs": 0,
  "total_sync_jobs": 0
}
```

**Example:**
```bash
curl http://localhost:8002/health
```

---

### Gmail Status

#### `GET /status`

Gets Gmail connection status and sync state for a user.

**Authentication:** None (called internally by API Gateway)

**Query Parameters:**
- `user_id` (string, required) - User email (from JWT `sub`)

**Response:**
```json
{
  "connected": true,
  "syncJobId": "550e8400-e29b-41d4-a716-446655440000" | null,
  "lockReason": "Sync in progress" | null
}
```

**Example:**
```bash
curl "http://localhost:8002/status?user_id=user@example.com"
```

**Status Codes:**
- `200 OK` - Status retrieved
- `503 Service Unavailable` - Service is down

---

### Sync Operations

#### `POST /sync/start`

Starts a Gmail sync job. Fetches ALL emails from Gmail (no limits).

**Authentication:** None (called internally by API Gateway)

**Request Body:**
```json
{
  "user_id": "user@example.com",
  "user_email": "user@example.com"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started"
}
```

**Example:**
```bash
curl -X POST http://localhost:8002/sync/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user@example.com",
    "user_email": "user@example.com"
  }'
```

**Status Codes:**
- `200 OK` - Sync started
- `403 Forbidden` - User ID does not match authenticated email
- `409 Conflict` - Sync already running (with job_id in detail)

**Notes:**
- Sync runs in the background.
- The sync fetches 100% of emails using pagination (`nextPageToken`).
- No hard limits (e.g., maxResults=1200) are applied.
- Email ownership is validated: Gmail email must match authenticated user email.

---

#### `GET /sync/progress/{job_id}`

Gets real-time sync progress for a job.

**Authentication:** None (called internally by API Gateway)

**Path Parameters:**
- `job_id` (string) - The sync job ID

**Query Parameters:**
- `user_id` (string, required) - User email (from JWT `sub`)

**Response:**
```json
{
  "status": "running" | "completed" | "failed",
  "total_scanned": 44000,
  "total_fetched": 44000,
  "candidate_job_emails": 1050,
  "classified": {
    "applied": 600,
    "rejected": 200,
    "interview": 50,
    "offer": 20,
    "ghosted": 180
  },
  "skipped": 42950,
  "applications_count": 1050,
  "stats": {
    "total": 1050,
    "applied": 600,
    "rejected": 200,
    "interview": 50,
    "offer": 20,
    "ghosted": 180
  }
}
```

**Example:**
```bash
curl "http://localhost:8002/sync/progress/550e8400-e29b-41d4-a716-446655440000?user_id=user@example.com"
```

**Status Codes:**
- `200 OK` - Progress retrieved
- `403 Forbidden` - Unauthorized (user_id mismatch)
- `404 Not Found` - Job not found

**Notes:**
- `total_scanned` - Total emails scanned in Gmail
- `total_fetched` - Total emails fetched (should match total_scanned for full sync)
- `candidate_job_emails` - Emails identified as job-related (Stage 1: High Recall)
- `classified` - Emails classified into 5 categories (Stage 2: High Precision)
- `skipped` - Emails that don't match job application criteria
- All counts are REAL, never estimated.

---

### Applications

#### `GET /applications`

Gets all applications with optional filtering. Returns ALL applications (no pagination limits).

**Authentication:** None (called internally by API Gateway)

**Query Parameters:**
- `user_id` (string, required) - User email (from JWT `sub`)
- `search` (string, optional) - Search by company name or role
- `status` (string, optional) - Filter by status: `applied`, `rejected`, `interview`, `offer`, `ghosted`

**Response:**
```json
{
  "applications": [
    {
      "id": 1,
      "company": "Tech Corp",
      "role": "Software Engineer",
      "status": "applied",
      "subject": "Application received",
      "from": "careers@techcorp.com",
      "date": "2024-01-15T10:00:00Z",
      "snippet": "Thank you for applying..."
    }
  ],
  "total": 1050,
  "counts": {
    "applied": 600,
    "rejected": 200,
    "interview": 50,
    "offer": 20,
    "ghosted": 180
  },
  "warning": null
}
```

**Example:**
```bash
# Get all applications
curl "http://localhost:8002/applications?user_id=user@example.com"

# Search for "Google"
curl "http://localhost:8002/applications?user_id=user@example.com&search=Google"

# Filter by status
curl "http://localhost:8002/applications?user_id=user@example.com&status=interview"
```

**Status Codes:**
- `200 OK` - Applications retrieved
- `500 Internal Server Error` - Failed to get applications

**Notes:**
- Returns ALL applications from the database (no frontend pagination limits).
- Use virtualized lists in the frontend for large datasets.

---

#### `GET /stats`

Gets dashboard statistics. Returns REAL counts from the database (never estimated).

**Authentication:** None (called internally by API Gateway)

**Query Parameters:**
- `user_id` (string, required) - User email (from JWT `sub`)

**Response:**
```json
{
  "total": 1050,
  "applied": 600,
  "rejected": 200,
  "interview": 50,
  "offer": 20,
  "ghosted": 180
}
```

**Example:**
```bash
curl "http://localhost:8002/stats?user_id=user@example.com"
```

**Status Codes:**
- `200 OK` - Stats retrieved
- `500 Internal Server Error` - Failed to get stats

**Notes:**
- All counts are calculated from the database.
- The `offer` category includes legacy `accepted` entries.
- Exactly 5 categories: `applied`, `rejected`, `interview`, `offer`, `ghosted`.

---

### Data Management

#### `POST /clear`

Clears all cached email data for a user. Called on logout or account switch.

**Authentication:** None (called internally by API Gateway)

**Request Body:**
```json
{
  "user_id": "user@example.com"
}
```

**Response:**
```json
{
  "message": "User data cleared"
}
```

**Example:**
```bash
curl -X POST http://localhost:8002/clear \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user@example.com"}'
```

**Status Codes:**
- `200 OK` - Data cleared successfully
- `500 Internal Server Error` - Failed to clear data

**Notes:**
- Deletes all applications for the user.
- Clears sync state (historyId, last_synced_at, locks).
- Removes sync jobs from memory.
- This is called automatically on logout or account switch.

---

#### `POST /ghosted/check`

Background job to check and update ghosted applications.

**Authentication:** None (called internally)

**Response:**
```json
{
  "message": "Ghosted check started"
}
```

**Example:**
```bash
curl -X POST http://localhost:8002/ghosted/check
```

**Notes:**
- Runs in the background.
- Checks applications that have been in "applied" status for more than `GHOSTED_DAYS` (default: 21 days).
- Moves qualifying applications to "ghosted" category.

---

## Database Schema

The service uses the following tables:

- **users** - User accounts
- **applications** - Job application emails
- **sync_states** - Gmail sync state per user

---

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Yes | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Yes | - |
| `REDIRECT_URI` | OAuth redirect URI | Yes | - |
| `DATABASE_URL` | PostgreSQL connection string | Yes | - |
| `CLASSIFIER_SERVICE_URL` | Classifier service URL | No | `http://classifier-service:8003` |
| `GHOSTED_DAYS` | Days before marking as ghosted | No | `21` |

---

## Sync Process

1. **Initial Full Sync:**
   - Uses `users.messages.list` with pagination (`nextPageToken`).
   - Fetches ALL emails (no limits).
   - Logs: `Fetched: X emails (100%)`.

2. **Incremental Sync:**
   - Uses `users.history.list` with stored `gmail_history_id`.
   - Fetches only new/changed messages.
   - Updates counts incrementally.

3. **Classification:**
   - Stage 1 (High Recall): Identifies candidate job emails.
   - Stage 2 (High Precision): Classifies into 5 categories.
   - Everything else is skipped (but counted).

4. **Sync Locking:**
   - DB-based lock with TTL (10 minutes).
   - Auto-releases on expiration or crash.
   - Prevents concurrent syncs.

---

## Error Responses

All endpoints may return standard error responses:

```json
{
  "detail": "Error message here"
}
```

**Common Status Codes:**
- `400 Bad Request` - Invalid request
- `403 Forbidden` - Unauthorized (email mismatch)
- `404 Not Found` - Resource not found
- `409 Conflict` - Sync already running
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service is down

---

## Notes

- Fetches 100% of emails (no hard limits).
- All counts are REAL from the database (never estimated).
- Email ownership is validated before sync.
- Sync locks prevent concurrent operations.
- Account switch triggers full data deletion.
