# Auth Service

**Port:** `8001`  
**Base URL:** `http://localhost:8001`  
**Service Name:** `auth-service`

The Auth Service handles Google OAuth authentication and JWT token issuance. It validates Google tokens and issues backend JWTs that are used across all services.

---

## Endpoints

### Health Check

#### `GET /health`

Returns the health status of the Auth Service.

**Authentication:** None

**Response:**
```json
{
  "status": "ok",
  "service": "auth-service",
  "timestamp": "2026-01-17T19:57:10Z",
  "uptime_seconds": 8.2,
  "google_oauth_configured": true | false
}
```

**Example:**
```bash
curl http://localhost:8001/health
```

---

### Authentication Endpoints

#### `GET /auth/login`

Initiates Google OAuth login. Returns the OAuth authorization URL for redirect.

**Authentication:** None

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/auth?client_id=...&redirect_uri=...&scope=..."
}
```

**Example:**
```bash
curl http://localhost:8001/auth/login
```

**Notes:**
- The `auth_url` should be used to redirect the user to Google's OAuth consent screen.
- After user consent, Google redirects to `REDIRECT_URI` with an authorization code.

---

#### `POST /auth/callback`

Exchanges the OAuth authorization code for a Google access token, validates it, and issues a backend JWT.

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
curl -X POST http://localhost:8001/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "4/0AeanS..."}'
```

**Status Codes:**
- `200 OK` - Token issued successfully
- `400 Bad Request` - Invalid authorization code or failed to handle callback

**Notes:**
- The frontend must store ONLY this backend JWT token.
- Google access tokens and refresh tokens are NOT returned to the frontend.
- The JWT contains: `sub` (email), `email`, `name`, and `exp` (expiration).

---

#### `GET /auth/me`

Verifies the backend JWT and returns the current user information.

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
curl http://localhost:8001/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Status Codes:**
- `200 OK` - User retrieved successfully
- `401 Unauthorized` - Missing or invalid Authorization header
- `401 Unauthorized` - Invalid or expired token

---

#### `POST /auth/logout`

Acknowledges logout. Actual data clearing is handled by the gmail-connector service.

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
  "message": "Logged out"
}
```

**Example:**
```bash
curl -X POST http://localhost:8001/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user@example.com"}'
```

**Notes:**
- This endpoint is typically called by the API Gateway during logout.
- The Auth Service does not maintain sessions; this is a stateless acknowledgment.

---

## JWT Token Structure

The JWT issued by the Auth Service contains:

```json
{
  "sub": "user@example.com",  // Subject (user email, used as user_id)
  "email": "user@example.com",
  "name": "John Doe",
  "exp": 1705612800  // Expiration timestamp (24 hours from issuance)
}
```

**Token Configuration:**
- **Algorithm:** HS256
- **Secret:** Set via `JWT_SECRET` environment variable
- **Expiration:** 24 hours (configurable via `JWT_EXPIRATION_HOURS`)

---

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `JWT_SECRET` | Secret key for JWT signing | Yes | - |
| `JWT_ALGORITHM` | JWT algorithm | No | `HS256` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Yes | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Yes | - |
| `REDIRECT_URI` | OAuth redirect URI | Yes | `http://localhost:8001/auth/callback` |
| `DATABASE_URL` | PostgreSQL connection string | No | - |

---

## OAuth Scopes

The Auth Service requests the following Google OAuth scopes:
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`

**Note:** Gmail scopes are NOT requested by the Auth Service. Gmail access is handled separately by the gmail-connector service.

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
- `500 Internal Server Error` - Server error

---

## Notes

- The Auth Service is stateless and does not store user sessions.
- All user identification is done via JWT tokens.
- Google OAuth tokens are never exposed to the frontend.
- The `sub` claim in the JWT (user email) is used as `user_id` across all services.
