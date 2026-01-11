# API Gateway

API Gateway for the Email Sync Job Dashboard. Routes requests to downstream services and enforces authentication and authorization.

## Features

- JWT authentication and verification
- Role-based access control (RBAC)
- Request ID generation and propagation
- CORS configuration
- Request proxying to auth-service and application-service
- Consistent error response format

## Local Development

### Prerequisites

- Python 3.11+
- auth-service running on port 8003
- application-service running on port 8002

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables (create `.env` file):
```env
# JWT (must match auth-service)
JWT_SECRET=change_me_to_secure_secret
JWT_ISSUER=email-sync-job-dashboard
JWT_AUDIENCE=email-sync-job-dashboard-users

# Service URLs
APPLICATION_SERVICE_URL=http://localhost:8002
AUTH_SERVICE_URL=http://localhost:8003

# CORS
CORS_ORIGINS=http://localhost:5173

# Service
SERVICE_PORT=8000
HTTP_TIMEOUT=30.0
```

3. Run the service:
```bash
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

### Health Check
- `GET /health` - Returns service status (no auth required)

### Authentication (Proxy to auth-service)
- `POST /auth/login` - Login (no JWT required)
- `POST /auth/refresh` - Refresh token (no JWT required)
- `POST /auth/logout` - Logout (JWT required)
- `GET /auth/me` - Get current user (JWT required)

### Applications (Proxy to application-service, JWT required)
- `GET /applications` - List applications (viewer/editor)
- `PATCH /applications/{id}` - Update application (editor only)

### Resumes (Proxy to application-service, JWT required)
- `POST /resumes/upload` - Upload resume (editor only)
- `GET /resumes` - List resumes (viewer/editor)

### Export (Proxy to application-service, JWT required)
- `GET /export/excel` - Export applications to Excel (viewer/editor)

## RBAC Rules

- **viewer**: Can only perform GET requests (read-only)
- **editor**: Can perform all HTTP methods (read and write)

If a viewer attempts a write operation (POST, PATCH, etc.), they will receive a 403 Forbidden error.

## JWT Enforcement

All endpoints except `/health`, `/auth/login`, and `/auth/refresh` require a valid JWT token in the `Authorization: Bearer <token>` header.

## Request Headers

The gateway adds the following headers to forwarded requests:
- `X-User-Id`: User ID from JWT
- `X-User-Email`: User email from JWT
- `X-User-Role`: User role from JWT
- `X-Request-Id`: Request tracking ID

All responses include `X-Request-Id` header.

## Error Format

All errors follow this format:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "request_id": "uuid-request-id"
  }
}
```

## Docker

Build and run:
```bash
docker build -t api-gateway .
docker run -p 8000:8000 --env-file .env api-gateway
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET` | Secret key for JWT verification (must match auth-service) | `change_me` |
| `JWT_ISSUER` | JWT issuer claim | `email-sync-job-dashboard` |
| `JWT_AUDIENCE` | JWT audience claim | `email-sync-job-dashboard-users` |
| `APPLICATION_SERVICE_URL` | URL of application-service | `http://application-service:8002` |
| `AUTH_SERVICE_URL` | URL of auth-service | `http://auth-service:8003` |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | `http://localhost:5173` |
| `SERVICE_PORT` | Gateway port | `8000` |
| `HTTP_TIMEOUT` | HTTP client timeout in seconds | `30.0` |
