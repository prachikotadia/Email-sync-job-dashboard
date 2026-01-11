# Auth Service

Authentication and authorization service for the Email Sync Job Dashboard.

## Features

- User authentication with email/password
- JWT-based access and refresh tokens
- Auto-user creation (dev-friendly)
- Role-based access control (viewer, editor)
- Token refresh and revocation
- Support for PostgreSQL and SQLite

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (optional, SQLite used by default)

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables (create `.env` file):
```env
AUTH_DATABASE_URL=sqlite:///./auth.db
# OR for PostgreSQL:
# AUTH_DATABASE_URL=postgresql://user:password@localhost:5432/authdb

JWT_SECRET=change_me_to_secure_secret
JWT_ISSUER=email-sync-job-dashboard
JWT_AUDIENCE=email-sync-job-dashboard-users
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=14
```

3. Run the service:
```bash
uvicorn app.main:app --reload --port 8003
```

The service will automatically create database tables on startup.

## API Endpoints

### Health Check
- `GET /health` - Returns service status

### Authentication
- `POST /auth/register` - Register a new user account
  - Body: `{ "email": "user@example.com", "password": "password123", "role": "viewer" }`
  - Returns: `{ "message": "User registered successfully", "user": {...} }`
  - First user automatically gets "editor" role, others get "viewer" (unless specified)
  - Password must be at least 8 characters
  - Email must be unique (returns 409 if exists)

- `POST /auth/login` - Login with email/password (existing users only)
  - Body: `{ "email": "user@example.com", "password": "password" }`
  - Returns: `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer", "user": {...} }`
  - Users must be registered first via `/auth/register`

- `POST /auth/refresh` - Refresh access token
  - Body: `{ "refresh_token": "..." }`
  - Returns: `{ "access_token": "...", "token_type": "bearer" }`

- `POST /auth/logout` - Logout (revoke refresh token)
  - Headers: `Authorization: Bearer <access_token>`
  - Body: `{ "refresh_token": "..." }`

- `GET /auth/me` - Get current user info
  - Headers: `Authorization: Bearer <access_token>`
  - Returns: `{ "id": "...", "email": "...", "role": "viewer|editor" }`

## Database Schema

### Users Table
- `id` (UUID, primary key)
- `email` (unique, indexed)
- `password_hash` (bcrypt)
- `role` ("viewer" | "editor")
- `created_at`

### Refresh Tokens Table
- `id` (UUID, primary key)
- `user_id` (foreign key to users)
- `token` (unique, indexed)
- `revoked` (boolean)
- `expires_at` (indexed)
- `created_at`

## Docker

Build and run:
```bash
docker build -t auth-service .
docker run -p 8003:8003 --env-file .env auth-service
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_DATABASE_URL` | Database connection string | `sqlite:///./auth.db` |
| `JWT_SECRET` | Secret key for JWT signing | `change_me` |
| `JWT_ISSUER` | JWT issuer claim | `email-sync-job-dashboard` |
| `JWT_AUDIENCE` | JWT audience claim | `email-sync-job-dashboard-users` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiry | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiry | `14` |
| `SERVICE_PORT` | Service port | `8003` |
