# API Endpoints Documentation

This document lists all available API endpoints in the Email Sync Job Dashboard system.

**Base URLs:**

- API Gateway: `http://localhost:8000` (Frontend should call this)
- Auth Service: `http://localhost:8003` (Internal)
- Application Service: `http://localhost:8002` (Internal)

---

## Status Legend

- ✅ **Implemented** - Fully functional and ready for use
- 🔄 **Proxied** - Endpoint exists in gateway, forwards to downstream service
- 🔒 **Auth Required** - JWT token required in Authorization header
- 👁️ **RBAC** - Role-based access control enforced

---

## API Gateway Endpoints

All frontend requests should go through the API Gateway at `http://localhost:8000`.

### Health Check

#### ✅ GET /health

**Status:** ✅ Implemented | **Auth:** ❌ Not Required

Check if the API Gateway is running.

**Response:**

```json
{
	"status": "ok"
}
```

---

### Authentication Endpoints

All auth endpoints are proxied to auth-service.

#### ✅ POST /auth/register

**Status:** ✅ Implemented | **Auth:** ❌ Not Required | **Proxied:** ✅

Register a new user account.

**Request Body:**

```json
{
	"email": "user@example.com",
	"password": "password123",
	"role": "viewer"
}
```

**Note:**

- `role` is optional. If not provided, first user gets "editor" role, subsequent users get "viewer" role
- Password must be at least 8 characters
- Email must be unique

**Response:**

```json
{
	"message": "User registered successfully",
	"user": {
		"id": "uuid-here",
		"email": "user@example.com",
		"role": "viewer"
	}
}
```

**Status Codes:**

- `201` - User created successfully
- `400` - Invalid request (invalid role or password too short)
- `409` - User already exists
- `500` - Server error

---

#### ✅ POST /auth/login

**Status:** ✅ Implemented | **Auth:** ❌ Not Required | **Proxied:** ✅

Login with email and password. Authenticates existing users only.

**Request Body:**

```json
{
	"email": "user@example.com",
	"password": "password123"
}
```

**Response:**

```json
{
	"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
	"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
	"token_type": "bearer",
	"user": {
		"id": "uuid-here",
		"email": "user@example.com",
		"role": "editor"
	}
}
```

**Status Codes:**

- `200` - Success
- `401` - Invalid email or password (user must be registered first)
- `500` - Server error

---

#### ✅ POST /auth/refresh

**Status:** ✅ Implemented | **Auth:** ❌ Not Required | **Proxied:** ✅

Refresh access token using refresh token.

**Request Body:**

```json
{
	"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**

```json
{
	"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
	"token_type": "bearer"
}
```

**Status Codes:**

- `200` - Success
- `401` - Invalid or expired refresh token
- `500` - Server error

---

#### ✅ POST /auth/logout

**Status:** ✅ Implemented | **Auth:** 🔒 Required | **Proxied:** ✅ | **RBAC:** ❌

Logout and revoke refresh token.

**Headers:**

```
Authorization: Bearer <access_token>
```

**Request Body:**

```json
{
	"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**

```json
{
	"message": "Logged out successfully"
}
```

**Status Codes:**

- `200` - Success
- `401` - Unauthorized
- `500` - Server error

---

#### ✅ GET /auth/me

**Status:** ✅ Implemented | **Auth:** 🔒 Required | **Proxied:** ✅ | **RBAC:** ❌

Get current authenticated user information.

**Headers:**

```
Authorization: Bearer <access_token>
```

**Response:**

```json
{
	"id": "uuid-here",
	"email": "user@example.com",
	"role": "editor"
}
```

**Status Codes:**

- `200` - Success
- `401` - Unauthorized
- `500` - Server error

---

### Application Endpoints

All application endpoints are proxied to application-service and require authentication.

#### ✅ GET /applications

**Status:** ✅ Implemented | **Auth:** 🔒 Required | **Proxied:** ✅ | **RBAC:** 👁️ (Viewer/Editor)

List all applications with optional filtering.

**Headers:**

```
Authorization: Bearer <access_token>
```

**Query Parameters:**

- `status` (optional) - Filter by application status

**Example:**

```
GET /applications?status=applied
```

**Response:**

```json
[
	{
		"id": "uuid-here",
		"company_name": "Acme Corp",
		"role_title": "Senior Engineer",
		"status": "applied",
		"applied_count": 1,
		"last_email_date": "2024-01-15T10:00:00Z",
		"ghosted": false,
		"resume_url": "path/to/resume.pdf"
	}
]
```

**Status Codes:**

- `200` - Success
- `401` - Unauthorized
- `403` - Forbidden (RBAC violation)
- `500` - Server error

---

#### ✅ PATCH /applications/{application_id}

**Status:** ✅ Implemented | **Auth:** 🔒 Required | **Proxied:** ✅ | **RBAC:** 👁️ (Editor only)

Update an application (status, resume, ghosted flag).

**Headers:**

```
Authorization: Bearer <access_token>
```

**Path Parameters:**

- `application_id` - UUID of the application

**Request Body:**

```json
{
	"status": "interviewed",
	"resume_id": "uuid-here",
	"ghosted": false
}
```

**Response:**

```json
{
	"id": "uuid-here",
	"company_name": "Acme Corp",
	"role_title": "Senior Engineer",
	"status": "interviewed",
	"applied_count": 1,
	"last_email_date": "2024-01-15T10:00:00Z",
	"ghosted": false,
	"resume_url": "path/to/resume.pdf"
}
```

**Status Codes:**

- `200` - Success
- `401` - Unauthorized
- `403` - Forbidden (Viewers cannot update)
- `404` - Application not found
- `500` - Server error

---

### Resume Endpoints

#### ✅ POST /resumes/upload

**Status:** ✅ Implemented | **Auth:** 🔒 Required | **Proxied:** ✅ | **RBAC:** 👁️ (Editor only)

Upload a resume file (PDF/DOC).

**Headers:**

```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Form Data:**

- `file` - Resume file (PDF/DOC)
- `tags` (optional) - Comma-separated tags (default: "general")

**Example:**

```
POST /resumes/upload
Content-Type: multipart/form-data

file: [binary file data]
tags: "frontend,fullstack"
```

**Response:**

```json
{
	"id": "uuid-here",
	"filename": "resume.pdf",
	"url": "uploads/resumes/uuid-here.pdf"
}
```

**Status Codes:**

- `200` - Success
- `401` - Unauthorized
- `403` - Forbidden (Viewers cannot upload)
- `500` - Server error

---

#### ✅ GET /resumes

**Status:** ✅ Implemented | **Auth:** 🔒 Required | **Proxied:** ✅ | **RBAC:** 👁️ (Viewer/Editor)

List all resumes.

**Headers:**

```
Authorization: Bearer <access_token>
```

**Response:**

```json
[
	{
		"id": "uuid-here",
		"name": "resume.pdf",
		"tags": ["frontend", "fullstack"],
		"created_at": "2024-01-15T10:00:00Z"
	}
]
```

**Status Codes:**

- `200` - Success
- `401` - Unauthorized
- `403` - Forbidden (RBAC violation)
- `500` - Server error

---

### Export Endpoints

#### ✅ GET /export/excel

**Status:** ✅ Implemented | **Auth:** 🔒 Required | **Proxied:** ✅ | **RBAC:** 👁️ (Viewer/Editor)

Export all applications to Excel file.

**Headers:**

```
Authorization: Bearer <access_token>
```

**Response:**

- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Body: Excel file binary data
- Headers include: `Content-Disposition: attachment; filename=applications_export_YYYYMMDD.xlsx`

**Status Codes:**

- `200` - Success
- `401` - Unauthorized
- `403` - Forbidden (RBAC violation)
- `500` - Server error

---

## Auth Service Endpoints (Internal)

These endpoints are called by the API Gateway. Frontend should use the gateway endpoints above.

### Health Check

#### ✅ GET /health

**Status:** ✅ Implemented | **Auth:** ❌ Not Required

**Response:**

```json
{
	"status": "ok"
}
```

### Authentication

#### ✅ POST /auth/register

**Status:** ✅ Implemented | **Auth:** ❌ Not Required

Same as gateway endpoint above.

#### ✅ POST /auth/login

**Status:** ✅ Implemented | **Auth:** ❌ Not Required

Same as gateway endpoint above.

#### ✅ POST /auth/refresh

**Status:** ✅ Implemented | **Auth:** ❌ Not Required

Same as gateway endpoint above.

#### ✅ POST /auth/logout

**Status:** ✅ Implemented | **Auth:** 🔒 Required

Same as gateway endpoint above.

#### ✅ GET /auth/me

**Status:** ✅ Implemented | **Auth:** 🔒 Required

Same as gateway endpoint above.

---

## RBAC (Role-Based Access Control)

### Roles

- **viewer**: Read-only access

  - ✅ GET requests allowed
  - ❌ POST, PATCH, PUT, DELETE requests blocked (403 Forbidden)

- **editor**: Full access
  - ✅ All HTTP methods allowed (GET, POST, PATCH, PUT, DELETE)

### Endpoint Access Matrix

| Endpoint             | Method | Viewer | Editor |
| -------------------- | ------ | ------ | ------ |
| `/health`            | GET    | ✅     | ✅     |
| `/auth/register`     | POST   | ✅     | ✅     |
| `/auth/login`        | POST   | ✅     | ✅     |
| `/auth/refresh`      | POST   | ✅     | ✅     |
| `/auth/logout`       | POST   | 🔒     | 🔒     |
| `/auth/me`           | GET    | 🔒     | 🔒     |
| `/applications`      | GET    | ✅     | ✅     |
| `/applications/{id}` | PATCH  | ❌     | ✅     |
| `/resumes`           | GET    | ✅     | ✅     |
| `/resumes/upload`    | POST   | ❌     | ✅     |
| `/export/excel`      | GET    | ✅     | ✅     |

---

## Authentication

### JWT Token Format

All authenticated endpoints require a JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Token Claims

JWT tokens contain the following claims:

- `sub`: User ID (UUID)
- `email`: User email address
- `role`: User role ("viewer" or "editor")
- `iss`: Issuer ("email-sync-job-dashboard")
- `aud`: Audience ("email-sync-job-dashboard-users")
- `exp`: Expiration time (Unix timestamp)
- `iat`: Issued at (Unix timestamp)

### Token Expiration

- **Access Token**: 60 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh Token**: 14 days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`)

---

## Error Response Format

All errors follow a consistent format:

```json
{
	"error": {
		"code": "ERROR_CODE",
		"message": "Human-readable error message",
		"request_id": "uuid-request-id"
	}
}
```

### Common Error Codes

- `AUTH_SERVICE_ERROR` - Error communicating with auth-service
- `APPLICATION_SERVICE_ERROR` - Error communicating with application-service
- `FORBIDDEN` - Insufficient permissions (RBAC violation)
- `UNAUTHORIZED` - Missing or invalid authentication token
- `INTERNAL_SERVER_ERROR` - Unexpected server error

### HTTP Status Codes

- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error
- `502` - Bad Gateway (downstream service unavailable)

---

## Request Headers

The gateway automatically adds the following headers to forwarded requests:

- `X-User-Id`: User ID from JWT token
- `X-User-Email`: User email from JWT token
- `X-User-Role`: User role from JWT token
- `X-Request-Id`: Request tracking ID (UUID)

All responses include `X-Request-Id` header for request tracing.

---

## Notes

1. **Frontend Integration**: Frontend should only call API Gateway endpoints at `http://localhost:8000`
2. **User Registration**: Users must register via `/auth/register` before they can login. First registered user automatically gets "editor" role, subsequent users get "viewer" role (unless specified in registration request)
3. **Token Refresh**: Use refresh token to obtain new access tokens before expiration
4. **RBAC Enforcement**: Gateway enforces RBAC rules; viewers receive 403 Forbidden for write operations
5. **CORS**: Gateway is configured to accept requests from `http://localhost:5173` (configurable)
6. **Password Requirements**: Minimum 8 characters required for registration

---

**Last Updated:** 2024-01-15
**Version:** 1.0.0
