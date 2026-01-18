# Google OAuth & Gmail Integration Implementation

## Overview

This document describes the complete Google OAuth login and Gmail integration implementation for the Email Sync Job Dashboard.

---

## Architecture

### Flow Diagram

```
┌─────────────┐
│  Frontend   │
│  (React)    │
└──────┬──────┘
       │
       │ 1. GET /api/auth/login
       ▼
┌─────────────┐
│ API Gateway │
└──────┬──────┘
       │
       │ 2. Proxy to Auth Service
       ▼
┌─────────────┐      ┌──────────────────┐
│Auth Service │─────▶│ Google OAuth API │
└──────┬──────┘      └──────────────────┘
       │
       │ 3. Return OAuth URL
       │
       ▼
┌─────────────┐
│  Frontend   │
│  (Redirect)  │
└──────┬──────┘
       │
       │ 4. User authorizes
       ▼
┌──────────────────┐
│ Google OAuth API │
└──────┬───────────┘
       │
       │ 5. Redirect with code
       ▼
┌─────────────┐
│  Frontend   │
│ /auth/callback│
└──────┬──────┘
       │
       │ 6. POST /api/auth/callback
       ▼
┌─────────────┐
│Auth Service │
└──────┬──────┘
       │
       │ 7. Exchange code for tokens
       │    Store tokens in Gmail Connector
       │    Create JWT
       │
       ▼
┌─────────────┐
│  Frontend   │
│  (JWT stored)│
└─────────────┘
```

---

## Components

### 1. Database Schema

**New Table: `oauth_tokens`**
- Stores Google OAuth access and refresh tokens
- Linked to users via `user_id`
- Encrypted in production (TODO)

**Fields:**
- `access_token`: Google OAuth access token
- `refresh_token`: Google OAuth refresh token (for token renewal)
- `token_uri`: OAuth token endpoint
- `client_id`: Google OAuth client ID
- `client_secret`: Google OAuth client secret
- `scopes`: JSON array of granted scopes
- `expires_at`: Token expiration timestamp

### 2. Auth Service Updates

**File: `services/auth-service/app/google_oauth.py`**
- Added `gmail.readonly` scope to OAuth request
- Enables Gmail API access during authentication

**File: `services/auth-service/app/main.py`**
- Updated `/auth/callback` endpoint to:
  1. Exchange OAuth code for tokens
  2. Store tokens in Gmail Connector service
  3. Create and return JWT token

### 3. Gmail Connector Service Updates

**File: `services/gmail-connector/app/database.py`**
- Added `OAuthToken` model for token storage
- Added relationship to `User` model

**File: `services/gmail-connector/app/main.py`**
- Added `/oauth/store` endpoint to receive tokens from Auth Service
- Updated `run_sync` to fetch OAuth tokens from database
- Updated `clear_user_data` to delete OAuth tokens on logout

**File: `services/gmail-connector/app/gmail_client.py`**
- Updated `GmailClient.__init__` to accept `OAuthToken` instance
- Implemented `_initialize_service` to build Gmail API service from stored tokens
- Removed placeholder code - now fully functional

---

## OAuth Scopes

The application requests the following Google OAuth scopes:

1. **`userinfo.email`** - Access user's email address
2. **`userinfo.profile`** - Access user's basic profile information
3. **`gmail.readonly`** - Read-only access to Gmail messages

> **Note:** `gmail.readonly` is sufficient for reading emails. No write permissions are needed.

---

## Security Considerations

### Current Implementation

✅ **Secure:**
- OAuth tokens stored in database (encrypted in production)
- JWT tokens used for frontend authentication
- Frontend never sees Google OAuth tokens directly
- Tokens deleted on logout

⚠️ **TODO for Production:**
- Encrypt OAuth tokens before storing in database
- Implement token refresh logic
- Add token expiration checks
- Rate limiting for OAuth endpoints
- Audit logging for token access

### Token Flow Security

1. **OAuth tokens** - Stored in database, only accessible by backend services
2. **JWT tokens** - Stored in frontend localStorage, used for API authentication
3. **Token validation** - JWT verified on every protected API call
4. **Token cleanup** - OAuth tokens deleted when user logs out

---

## API Endpoints

### Auth Service

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | GET | Get Google OAuth URL |
| `/auth/callback` | POST | Exchange code for tokens and JWT |
| `/auth/me` | GET | Get current user (requires JWT) |
| `/auth/logout` | POST | Logout user |

### Gmail Connector Service

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/oauth/store` | POST | Store OAuth tokens (called by Auth Service) |
| `/sync/start` | POST | Start Gmail sync (requires JWT) |
| `/sync/progress/{job_id}` | GET | Get sync progress (requires JWT) |
| `/status` | GET | Get Gmail connection status (requires JWT) |
| `/clear` | POST | Clear user data and tokens (requires JWT) |

---

## Environment Variables

Required environment variables (see `.env.example`):

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
REDIRECT_URI=http://localhost:3000/auth/callback

# JWT
JWT_SECRET=your-strong-random-secret
JWT_ALGORITHM=HS256

# Database
DATABASE_URL=postgresql://user:password@db:5432/dbname
```

---

## Testing the Implementation

### 1. Start Services

```bash
docker-compose up --build
```

### 2. Verify Health

```bash
# Auth Service
curl http://localhost:8001/health

# Gmail Connector Service
curl http://localhost:8002/health

# API Gateway
curl http://localhost:8000/health
```

### 3. Test Login Flow

1. Open http://localhost:3000
2. Click "Sign in with Google"
3. Authorize the application
4. Verify redirect back to app
5. Check that JWT is stored in localStorage
6. Verify user can access dashboard

### 4. Test Gmail Sync

1. After login, click "Start Sync"
2. Verify sync progress updates
3. Check applications are fetched and classified
4. Verify emails appear in dashboard

### 5. Verify Token Storage

```bash
# Check database for stored tokens
docker-compose exec db psql -U jobpulse -d jobpulse_db -c "SELECT u.email, ot.scopes FROM users u JOIN oauth_tokens ot ON u.id = ot.user_id;"
```

---

## Troubleshooting

### Common Issues

**1. "No OAuth tokens found"**
- **Cause:** User hasn't completed OAuth flow
- **Solution:** Re-authenticate via login

**2. "Access token expired"**
- **Cause:** Token expired and refresh not implemented
- **Solution:** Re-authenticate (refresh logic TODO)

**3. "Gmail service not initialized"**
- **Cause:** Invalid or missing OAuth tokens
- **Solution:** Check token storage, re-authenticate

**4. "Email mismatch"**
- **Cause:** Gmail account doesn't match authenticated user
- **Solution:** Use same Google account for login and Gmail

---

## Next Steps

### Immediate TODOs

- [ ] Implement token refresh logic
- [ ] Add token expiration checks
- [ ] Encrypt OAuth tokens in database
- [ ] Add comprehensive error handling
- [ ] Add token refresh background job

### Future Enhancements

- [ ] Support multiple Gmail accounts per user
- [ ] Token rotation and refresh automation
- [ ] OAuth token audit logging
- [ ] Rate limiting for OAuth endpoints
- [ ] Support for Google Workspace accounts

---

## References

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Setup Instructions](./GOOGLE_CLOUD_SETUP.md)
- [Quick Setup Guide](./QUICK_SETUP.md)
