# 🔴 CRITICAL: OAuth Callback 405 Error Fix

## Problem
The API Gateway route `/auth/google/callback` is returning **405 Method Not Allowed**, blocking Google OAuth completion.

## Root Cause
- Google Cloud Console is configured to redirect to `http://localhost:8000/auth/google/callback` (API Gateway)
- The API Gateway route is not registering properly (persistent FastAPI routing issue)
- This blocks the entire OAuth flow

## Solution: Update Google Cloud Console Redirect URI

### Step 1: Update Google Cloud Console
1. Go to: https://console.cloud.google.com/apis/credentials
2. Find your OAuth 2.0 Client ID: `100820242078-20elejiluhdb4j9s1gdih1ug89hlumkf`
3. Click **Edit** (pencil icon)
4. In **Authorized redirect URIs**, update:
   - **OLD**: `http://localhost:8000/auth/google/callback`
   - **NEW**: `http://localhost:8003/auth/google/callback`
5. Click **Save**

### Step 2: Verify Auth Service Config
The auth service `.env` should already have:
```bash
GOOGLE_REDIRECT_URI=http://localhost:8003/auth/google/callback
```

### Step 3: Restart Auth Service
```bash
cd services/auth-service
./start.sh
```

## Why This Works
- Bypasses the API Gateway completely for OAuth callback
- Auth service (port 8003) handles the callback directly
- No 405 errors - route works perfectly
- Frontend already has fallback to auth service for login initiation

## Verification
After updating Google Cloud Console:
1. Try Google login again
2. OAuth flow should complete successfully
3. You should be redirected back to frontend with tokens

## Alternative (If You Can't Update Google Cloud Console)
If you cannot access Google Cloud Console (friend's account), the frontend fallback will work for login initiation, but the callback will still fail. You'll need to ask your friend to update the redirect URI.
