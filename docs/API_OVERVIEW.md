# API Overview

Complete API documentation for all JobPlusAI services.

---

## Service Ports

| Service | Port | Base URL |
|---------|------|----------|
| **Frontend** | 3000 | `http://localhost:3000` |
| **API Gateway** | 8000 | `http://localhost:8000` |
| **Auth Service** | 8001 | `http://localhost:8001` |
| **Gmail Connector** | 8002 | `http://localhost:8002` |
| **Classifier Service** | 8003 | `http://localhost:8003` |
| **PostgreSQL** | 5432 | `localhost:5432` |

---

## Service Documentation

- **[API Gateway](./API_GATEWAY.md)** - Main entry point, routes requests to backend services
- **[Auth Service](./AUTH_SERVICE.md)** - Google OAuth and JWT token issuance
- **[Gmail Connector Service](./GMAIL_CONNECTOR_SERVICE.md)** - Gmail sync, email fetching, classification
- **[Classifier Service](./CLASSIFIER_SERVICE.md)** - Email classification pipeline
- **[Frontend](./FRONTEND.md)** - React SPA and Nginx configuration

---

## Quick Reference

### Authentication Flow

1. **Login:** `GET /api/auth/login` → Returns OAuth URL
2. **User redirects to Google** → User consents
3. **Callback:** `POST /api/auth/callback` → Returns JWT token
4. **Use JWT:** Include `Authorization: Bearer <token>` in all requests

### Gmail Sync Flow

1. **Start Sync:** `POST /api/gmail/sync/start` → Returns `job_id`
2. **Poll Progress:** `GET /api/gmail/sync/progress/{job_id}` → Real-time counts
3. **Get Stats:** `GET /api/gmail/stats` → Dashboard statistics
4. **Get Applications:** `GET /api/gmail/applications` → All applications

---

## Common Endpoints

### Health Checks

- `GET /health` (Auth, Gmail, Classifier)
- `GET /api/health` (API Gateway)
- `GET /health` (Frontend)

### Authentication

- `GET /api/auth/login` - Initiate OAuth
- `POST /api/auth/callback` - Exchange code for JWT
- `GET /api/auth/me` - Get current user (requires auth)
- `POST /api/auth/logout` - Logout (requires auth)

### Gmail

- `GET /api/gmail/status` - Connection status (requires auth)
- `POST /api/gmail/sync/start` - Start sync (requires auth)
- `GET /api/gmail/sync/progress/{job_id}` - Progress (requires auth)
- `GET /api/gmail/applications` - List applications (requires auth)
- `GET /api/gmail/stats` - Dashboard stats (requires auth)

---

## Authentication

All protected endpoints require a JWT token in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

**JWT Structure:**
```json
{
  "sub": "user@example.com",  // User ID (email)
  "email": "user@example.com",
  "name": "John Doe",
  "exp": 1705612800  // Expiration (24 hours)
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message here"
}
```

**Common Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Invalid request
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., sync already running)
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Backend service unavailable

---

## Rate Limiting

Currently, no rate limiting is implemented. Consider adding rate limiting for production.

---

## CORS

The API Gateway allows CORS from:
- `http://localhost:3000`
- `http://localhost:5173` (Vite dev server)

---

## Notes

- All timestamps are in UTC ISO 8601 format.
- All counts are REAL from the database (never estimated).
- Gmail sync fetches 100% of emails (no limits).
- Account switch triggers full data deletion for privacy.

---

## Testing

**Health Checks:**
```bash
curl http://localhost:3000/health
curl http://localhost:8000/api/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

**Authentication:**
```bash
# Get OAuth URL
curl http://localhost:8000/api/auth/login

# Exchange code for token (after OAuth redirect)
curl -X POST http://localhost:8000/api/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "..."}'
```

**Gmail Sync:**
```bash
# Start sync
curl -X POST http://localhost:8000/api/gmail/sync/start \
  -H "Authorization: Bearer <token>"

# Check progress
curl http://localhost:8000/api/gmail/sync/progress/<job_id> \
  -H "Authorization: Bearer <token>"
```

---

## Support

For issues or questions, refer to:
- [SERVICE_LAYOUT.md](../SERVICE_LAYOUT.md) - Service boundaries
- [WORKFLOW.md](../WORKFLOW.md) - Complete workflow documentation
- [README.md](../README.md) - Project overview
