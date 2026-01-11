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
| `GMAIL_SERVICE_URL` | URL of gmail-connector-service | `http://localhost:8001` |
| `GOOGLE_REDIRECT_URI` | **REQUIRED** - Google OAuth redirect URI (must match Google Cloud Console) | `http://localhost:8000/auth/gmail/callback` |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | `http://localhost:5173` |
| `ENV` | Environment (dev, staging, production) | `dev` |
| `SERVICE_PORT` | Gateway port | `8000` |
| `HTTP_TIMEOUT` | HTTP client timeout in seconds | `30.0` |

## Google OAuth Configuration

### Setting Up Google Cloud Console

The `GOOGLE_REDIRECT_URI` environment variable **MUST** match exactly what you register in Google Cloud Console.

#### Step 1: Configure Environment Variable

In your `.env` file, you can use EITHER:

**Option A: Gateway URL (recommended for production)**
```env
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
```

**Option B: Gmail Connector Service URL (if already configured in Google Cloud Console)**
```env
GOOGLE_REDIRECT_URI=http://localhost:8001/auth/gmail/callback
```

For production:
```env
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/gmail/callback
```

**Important**: The redirect URI must match EXACTLY what's registered in Google Cloud Console.

#### Step 2: Register in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Click on your **OAuth 2.0 Client ID**
4. Scroll to **Authorized redirect URIs**
5. Click **+ ADD URI**
6. **Add EXACTLY this URI** (must match your `.env` file `GOOGLE_REDIRECT_URI`):
   
   **If using gateway URL:**
   ```
   http://localhost:8000/auth/gmail/callback
   ```
   
   **If using gmail-connector-service URL:**
   ```
   http://localhost:8001/auth/gmail/callback
   ```
   
   **For production:**
   ```
   https://yourdomain.com/auth/gmail/callback
   ```

7. Click **SAVE**

**Note**: If you already have a redirect URI registered in Google Cloud Console, use that exact URI in your `.env` file. The code will work with either gateway or gmail-connector-service URLs.

#### Important Notes

- **Must match exactly**: The URI in `.env` and Google Cloud Console must be **identical** (character-for-character)
- **No trailing slash**: Do NOT include a trailing slash (e.g., use `/auth/gmail/callback`, not `/auth/gmail/callback/`)
- **localhost vs 127.0.0.1**: Google treats `localhost` and `127.0.0.1` as different. If you're having issues, try adding both:
  - `http://localhost:8000/auth/gmail/callback`
  - `http://127.0.0.1:8000/auth/gmail/callback`
- **HTTP vs HTTPS**: 
  - Local development: Use `http://`
  - Production: Use `https://`
- **Port number**: The port must match your gateway's `SERVICE_PORT` (default: 8000)

#### Verify Configuration

In development mode (`ENV=dev`), you can verify your configuration:

```bash
curl http://localhost:8000/debug/oauth
```

This returns:
```json
{
  "redirect_uri": "http://localhost:8000/auth/gmail/callback",
  "gateway_base_url": "http://localhost:8000",
  "note": "Register this exact redirect_uri in Google Cloud Console 'Authorized redirect URIs'",
  "google_cloud_console_instructions": {
    "step_1": "Go to Google Cloud Console → APIs & Services → Credentials",
    "step_2": "Click on your OAuth 2.0 Client ID",
    "step_3": "Under 'Authorized redirect URIs', add exactly: http://localhost:8000/auth/gmail/callback",
    "step_4": "Click Save"
  }
}
```

Copy the `redirect_uri` value and paste it into Google Cloud Console.

### OAuth Flow Architecture

The gateway owns the OAuth flow:

1. **Entry Point**: `GET /gmail/connect` (redirects browser to Google)
2. **Callback**: `GET /auth/gmail/callback` (receives callback from Google)
3. **Internal**: Gateway forwards to gmail-connector-service internal endpoints

The redirect URI is managed in a single place (`GOOGLE_REDIRECT_URI` env var) and validated on startup.
