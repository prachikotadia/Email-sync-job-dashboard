# API Gateway Service

**Port:** `8000`  
**Base URL:** `http://localhost:8000`  
**Service Name:** `api-gateway`

The API Gateway is the single entry point for all client requests. It routes requests to appropriate backend services and handles authentication.

---

## Endpoints

### Health Check

#### `GET /api/health`

Returns the health status of the API Gateway and its dependencies.

**Authentication:** None

**Response:**
```json
{
  "status": "ok" | "degraded",
  "service": "api-gateway",
  "timestamp": "2026-01-17T19:57:07Z",
  "uptime_seconds": 4.88,
  "dependencies": {
    "auth_service": {
      "status": "ok" | "error",
      "status_code": 200,
      "latency_ms": 13
    },
    "gmail_service": {
      "status": "ok" | "error",
      "status_code": 200,
      "latency_ms": 31
    },
    "classifier_service": {
      "status": "ok" | "error",
      "status_code": 200,
      "latency_ms": 6
    }
  }
}
```

**Status Codes:**
- `200 OK` - Service is healthy
- `503 Service Unavailable` - Service is degraded (one or more dependencies failed)

---

## Authentication Endpoints

All authentication endpoints are prefixed with `/api/auth`.

### `GET /api/auth/login`

Initiates Google OAuth login flow.

**Authentication:** None

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/auth?..."
}
```

**Example:**
```bash
curl http://localhost:8000/api/auth/login
```

---

### `POST /api/auth/callback`

Handles OAuth callback and returns JWT token.

**Authentication:** None

**Request Body:**
```json
{
  "code": "4/0AeanS..."
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "4/0AeanS..."}'
```

---

### `GET /api/auth/me`

Returns the current authenticated user.

**Authentication:** Required (Bearer token)

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "email": "user@example.com",
  "name": "John Doe"
}
```

**Example:**
```bash
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Status Codes:**
- `200 OK` - User retrieved successfully
- `401 Unauthorized` - Invalid or missing token

---

### `POST /api/auth/logout`

Logs out the user and clears all cached email data.

**Authentication:** Required (Bearer token)

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Gmail Endpoints

All Gmail endpoints are prefixed with `/api/gmail` and require authentication.

### `GET /api/gmail/status`

Gets Gmail connection status and sync state.

**Authentication:** Required (Bearer token)

**Headers:**
```
Authorization: Bearer <jwt_token>
```

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
curl http://localhost:8000/api/gmail/status \
  -H "Authorization: Bearer <token>"
```

**Status Codes:**
- `200 OK` - Status retrieved
- `503 Service Unavailable` - Gmail service is down

---

### `POST /api/gmail/sync/start`

Starts a Gmail sync job.

**Authentication:** Required (Bearer token)

**Headers:**
```
Authorization: Bearer <jwt_token>
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
curl -X POST http://localhost:8000/api/gmail/sync/start \
  -H "Authorization: Bearer <token>"
```

**Status Codes:**
- `200 OK` - Sync started
- `409 Conflict` - Sync already running
- `503 Service Unavailable` - Gmail service is down

---

### `GET /api/gmail/sync/progress/{job_id}`

Gets real-time sync progress for a job.

**Authentication:** Required (Bearer token)

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Path Parameters:**
- `job_id` (string) - The sync job ID

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
curl http://localhost:8000/api/gmail/sync/progress/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer <token>"
```

**Status Codes:**
- `200 OK` - Progress retrieved
- `404 Not Found` - Job not found
- `503 Service Unavailable` - Gmail service is down

---

### `GET /api/gmail/applications`

Gets all applications with optional filtering.

**Authentication:** Required (Bearer token)

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Query Parameters:**
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
    "rejected": 200
  },
  "warning": null
}
```

**Example:**
```bash
# Get all applications
curl http://localhost:8000/api/gmail/applications \
  -H "Authorization: Bearer <token>"

# Search for "Google"
curl "http://localhost:8000/api/gmail/applications?search=Google" \
  -H "Authorization: Bearer <token>"

# Filter by status
curl "http://localhost:8000/api/gmail/applications?status=interview" \
  -H "Authorization: Bearer <token>"
```

**Status Codes:**
- `200 OK` - Applications retrieved
- `500 Internal Server Error` - Failed to get applications
- `503 Service Unavailable` - Gmail service is down

---

### `GET /api/gmail/stats`

Gets dashboard statistics (real counts from database).

**Authentication:** Required (Bearer token)

**Headers:**
```
Authorization: Bearer <jwt_token>
```

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
curl http://localhost:8000/api/gmail/stats \
  -H "Authorization: Bearer <token>"
```

**Status Codes:**
- `200 OK` - Stats retrieved
- `500 Internal Server Error` - Failed to get stats
- `503 Service Unavailable` - Gmail service is down

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
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., sync already running)
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Backend service unavailable

---

## Notes

- All authenticated endpoints require a valid JWT token in the `Authorization` header.
- The API Gateway proxies requests to backend services (auth-service, gmail-connector-service, classifier-service).
- Health check includes dependency status for monitoring.
- All timestamps are in UTC ISO 8601 format.
