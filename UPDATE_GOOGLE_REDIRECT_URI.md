# 🔧 UPDATE GOOGLE CLOUD CONSOLE REDIRECT URI

## Problem
Google OAuth is redirecting to `http://localhost:8000/auth/google/callback` (API Gateway) which returns 405 error.

## Solution
Update Google Cloud Console to use auth service directly.

## Steps

1. **Go to Google Cloud Console:**
   - https://console.cloud.google.com/apis/credentials

2. **Find your OAuth 2.0 Client ID:**
   - Client ID: `100820242078-20elejiluhdb4j9s1gdih1ug89hlumkf`
   - Click on it to edit

3. **Update Authorized redirect URIs:**
   - Find "Authorized redirect URIs" section
   - **ADD or UPDATE** this URI:
     ```
     http://localhost:8003/auth/google/callback
     ```
   - You can keep the old one (`http://localhost:8000/auth/google/callback`) or remove it
   - Click **SAVE**

4. **Restart auth service:**
   ```bash
   # Auth service should restart automatically
   # Or manually:
   cd services/auth-service
   ./start.sh
   ```

5. **Test:**
   - Try Google login again
   - It should redirect to port 8003 and work!

## Why This Works
- Auth service callback route works (returns 302 redirect)
- Bypasses API Gateway 405 error completely
- Direct connection to auth service is more reliable

## Alternative: Fix API Gateway (Future)
If you want to use API Gateway later, you'll need to:
1. Fix the API Gateway route registration issue
2. Update redirect URI back to port 8000
3. Update Google Cloud Console again

For now, using port 8003 directly is the fastest solution.
