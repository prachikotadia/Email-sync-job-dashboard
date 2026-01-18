# OAuth 2.0 + OpenID Connect Implementation

## Overview

This document describes the production-ready Google OAuth 2.0 and OpenID Connect implementation that eliminates scope mismatch errors and provides secure authentication.

## Key Features

### 1. Explicit Scope Management
- **Problem**: Google automatically adds `openid` scope when using userinfo endpoints, causing "Scope has changed" warnings
- **Solution**: Explicitly include `openid` in `OAUTH_SCOPES` to match what Google returns
- **Location**: `app/oauth_config.py`

### 2. Consistent Scope Usage
- Same scopes used in:
  - Authorization URL generation (`get_authorization_url()`)
  - Token exchange (`exchange_code()`)
- Prevents scope mismatch errors

### 3. CSRF Protection
- State parameter generated and validated
- Stored in memory (production: use Redis/session store)

### 4. OpenID Connect Support
- ID token verification when available
- Validates issuer, audience, and expiration
- Uses `google.oauth2.id_token` for verification

### 5. Comprehensive Error Handling
- Scope validation with detailed error messages
- Logs requested vs returned scopes
- Never swallows OAuth errors silently

### 6. Security Best Practices
- Never logs access tokens or refresh tokens
- State parameter validation
- HTTPS-only redirect URIs (documented for dev exceptions)

## Architecture

```
app/
├── oauth_config.py      # OAuth scopes and configuration constants
├── google_oauth.py       # OAuth flow implementation
├── main.py              # FastAPI route handlers
└── jwt.py               # JWT token creation/verification
```

## OAuth Scopes

Defined in `app/oauth_config.py`:

```python
OAUTH_SCOPES = [
    "openid",  # REQUIRED - Prevents scope mismatch warnings
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
]
```

## Flow

1. **Login** (`GET /auth/login`)
   - Generates authorization URL with consistent scopes
   - Returns `auth_url` and `state` token

2. **Callback** (`POST /auth/callback`)
   - Receives authorization code and state
   - Exchanges code for tokens using SAME scopes
   - Validates returned scopes match requested scopes
   - Verifies ID token (if present)
   - Stores OAuth tokens in gmail-connector service
   - Issues backend JWT token

3. **User Info** (`GET /auth/me`)
   - Verifies backend JWT
   - Returns user information

## Common Pitfalls

### 1. Scope Mismatch
**Problem**: "Scope has changed from ... to ... openid"

**Cause**: Not explicitly requesting `openid` scope

**Solution**: Always include `openid` in `OAUTH_SCOPES`

### 2. Redirect URI Mismatch
**Problem**: "redirect_uri_mismatch" error

**Cause**: Redirect URI doesn't match exactly in:
- Authorization URL
- Token exchange
- Google Cloud Console

**Solution**: Use consistent `REDIRECT_URI` environment variable everywhere

### 3. Missing Refresh Tokens
**Problem**: No refresh token returned

**Cause**: Not using `access_type="offline"` and `prompt="consent"`

**Solution**: Already configured in `oauth_config.py`

### 4. State Parameter Not Validated
**Problem**: CSRF vulnerability

**Solution**: Always validate state parameter in callback

## Testing

### Scope Validation Function

The `validate_scopes()` function in `oauth_config.py` ensures:
- All requested scopes are present in returned scopes
- Unexpected scopes are identified (except expected `openid`)

### Manual Testing

1. **Test Login Flow**:
   ```bash
   curl http://localhost:8001/auth/login
   ```

2. **Test Callback** (after OAuth redirect):
   ```bash
   curl -X POST http://localhost:8001/auth/callback \
     -H "Content-Type: application/json" \
     -d '{"code": "authorization_code", "state": "state_token"}'
   ```

## Environment Variables

Required:
- `GOOGLE_CLIENT_ID`: Google OAuth 2.0 client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth 2.0 client secret
- `REDIRECT_URI`: OAuth redirect URI (must match Google Cloud Console)
- `JWT_SECRET`: Secret for JWT token signing
- `GMAIL_SERVICE_URL`: URL of gmail-connector service

## Production Checklist

- [ ] Use HTTPS for redirect URIs
- [ ] Store state in Redis/session (not in-memory)
- [ ] Rotate JWT_SECRET regularly
- [ ] Monitor OAuth errors and scope mismatches
- [ ] Restrict CORS origins to frontend domain
- [ ] Enable ID token verification
- [ ] Implement refresh token rotation
- [ ] Add rate limiting for OAuth endpoints
- [ ] Log security events (not tokens)

## Security Notes

1. **Never log tokens**: Access tokens and refresh tokens are never logged
2. **State validation**: Always validate state parameter to prevent CSRF
3. **Scope validation**: Always validate returned scopes match requested scopes
4. **ID token verification**: Verify ID tokens when available for additional security
5. **HTTPS only**: In production, all redirect URIs must use HTTPS
