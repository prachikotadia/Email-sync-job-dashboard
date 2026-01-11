# How to Verify Redirect URI Configuration

This guide shows you how to check if your OAuth redirect URI is correctly configured and working.

## Step 1: Check Current Configuration

### Option A: Use Debug Endpoint (Development Only)

If your API Gateway is running with `ENV=dev`, you can check the current redirect URI configuration:

```bash
curl http://localhost:8000/debug/oauth
```

Expected response:
```json
{
  "redirect_uri": "http://localhost:8001/auth/gmail/callback",
  "gateway_base_url": "http://localhost:8000",
  "redirect_target": "gmail-connector-service",
  "note": "Register this exact redirect_uri in Google Cloud Console 'Authorized redirect URIs'. This URI must match EXACTLY what's in your .env file.",
  "google_cloud_console_instructions": {
    "step_1": "Go to Google Cloud Console → APIs & Services → Credentials",
    "step_2": "Click on your OAuth 2.0 Client ID",
    "step_3": "Under 'Authorized redirect URIs', add exactly: http://localhost:8001/auth/gmail/callback",
    "step_4": "Click Save",
    "important": "The redirect URI in Google Cloud Console must match EXACTLY the GOOGLE_REDIRECT_URI in your .env file (character-for-character, including port number)"
  }
}
```

**What to check:**
- ✅ `redirect_uri` matches what you expect
- ✅ `redirect_target` shows whether it points to "gateway" or "gmail-connector-service"

### Option B: Check Environment Variables

Check your `.env` files:

**API Gateway** (`services/api-gateway/.env`):
```bash
cat services/api-gateway/.env | grep GOOGLE_REDIRECT_URI
```

**Gmail Connector Service** (`services/gmail-connector-service/.env`):
```bash
cat services/gmail-connector-service/.env | grep GOOGLE_REDIRECT_URI
```

## Step 2: Verify Google Cloud Console Configuration

1. **Go to Google Cloud Console:**
   - Navigate to: https://console.cloud.google.com/
   - Go to **APIs & Services** → **Credentials**

2. **Open your OAuth 2.0 Client ID:**
   - Click on your OAuth 2.0 Client ID
   - Scroll to **"Authorized redirect URIs"**

3. **Verify the URI matches EXACTLY:**
   - Check if your redirect URI from Step 1 is listed
   - **IMPORTANT**: The URI must match **character-for-character**
   - Common issues:
     - ❌ Trailing slash: `http://localhost:8001/auth/gmail/callback/` (wrong)
     - ✅ No trailing slash: `http://localhost:8001/auth/gmail/callback` (correct)
     - ❌ Wrong port: `http://localhost:8000/auth/gmail/callback` (if you configured 8001)
     - ✅ Correct port: `http://localhost:8001/auth/gmail/callback` (matches your config)

4. **If it doesn't match:**
   - Click **"+ ADD URI"**
   - Add the exact URI from your `.env` file
   - Click **"SAVE"**

## Step 3: Test the OAuth Flow

### Test 1: Check Service Health

**API Gateway:**
```bash
curl http://localhost:8000/health
```

**Gmail Connector Service:**
```bash
curl http://localhost:8001/health
```

Both should return `{"status": "ok"}` or similar.

### Test 2: Start the OAuth Flow

1. **Make sure you're logged in** to your application
2. **Navigate to Settings page** (http://localhost:5173/settings)
3. **Click "Connect with Google"** button
4. **Watch the browser URL:**
   - You should be redirected to Google's OAuth consent screen
   - **Check the URL in the address bar** - it should contain `redirect_uri=` parameter
   - Verify the `redirect_uri` parameter matches your configuration

### Test 3: Check OAuth Authorization URL

**Option A: Using the API directly (requires JWT token):**

1. Get your JWT token (from browser localStorage or login response)
2. Call the API:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/gmail/auth/url
```

3. Check the response:
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "..."
}
```

4. **Extract and decode the redirect_uri:**
   - Copy the `auth_url` value
   - Decode the URL or inspect it in the browser
   - Look for `redirect_uri=` parameter
   - Verify it matches your configuration

**Option B: Check browser network tab:**

1. Open browser Developer Tools (F12)
2. Go to **Network** tab
3. Click "Connect with Google"
4. Find the request to `/gmail/auth/url` or `/gmail/connect`
5. Check the response - it should contain `auth_url`
6. Copy the `auth_url` and decode/inspect it
7. Verify the `redirect_uri` parameter matches your config

### Test 4: Complete the OAuth Flow

1. **Start the OAuth flow** (click "Connect with Google")
2. **Complete the authorization** on Google's consent screen
3. **Watch what happens:**
   - ✅ **Success**: You should be redirected to your frontend Settings page with `?gmail_connected=true`
   - ❌ **Error**: You'll be redirected with `?gmail_error=redirect_uri_mismatch` or similar

## Step 4: Common Issues and Solutions

### Issue 1: "redirect_uri_mismatch" Error

**Symptoms:**
- OAuth flow starts successfully
- After authorization, you get `redirect_uri_mismatch` error
- Redirected to frontend with `?gmail_error=redirect_uri_mismatch`

**Solution:**
1. Check your `.env` file - note the exact `GOOGLE_REDIRECT_URI`
2. Check Google Cloud Console - verify the URI is registered exactly
3. Common mistakes:
   - Trailing slash mismatch
   - Port number mismatch (8000 vs 8001)
   - Protocol mismatch (http vs https)
   - Case sensitivity (shouldn't matter, but verify)
   - Extra spaces or characters

**Quick Fix:**
```bash
# 1. Get your current redirect URI
curl http://localhost:8000/debug/oauth | grep redirect_uri

# 2. Copy the exact URI from the response

# 3. Go to Google Cloud Console and make sure this EXACT URI is registered
```

### Issue 2: Callback Not Received

**Symptoms:**
- OAuth flow starts
- Authorization completes
- But callback is never received (no redirect back)

**Check:**
1. **Is the redirect URI pointing to the correct service?**
   - If `GOOGLE_REDIRECT_URI=http://localhost:8001/auth/gmail/callback`:
     - Gmail Connector Service must be running on port 8001
   - If `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback`:
     - API Gateway must be running on port 8000

2. **Check service logs:**
   ```bash
   # API Gateway logs (if redirect goes through gateway)
   # Gmail Connector Service logs (if redirect goes directly)
   ```

3. **Check firewall/network:**
   - Make sure the port is accessible
   - Check if any firewall is blocking the callback

### Issue 3: Services Not Running

**Check if services are running:**
```bash
# Check API Gateway (port 8000)
curl http://localhost:8000/health

# Check Gmail Connector Service (port 8001)
curl http://localhost:8001/health

# Check what's using the ports
netstat -ano | findstr :8000  # Windows
netstat -ano | findstr :8001  # Windows

# Or
lsof -i :8000  # Linux/Mac
lsof -i :8001  # Linux/Mac
```

### Issue 4: Environment Variable Not Loaded

**Check if environment variable is set:**
```bash
# In API Gateway directory
cd services/api-gateway
cat .env | grep GOOGLE_REDIRECT_URI

# Verify the service is reading it:
# Check startup logs for "Google OAuth redirect URI validated: ..."
```

**If not set:**
1. Create/update `.env` file
2. Add: `GOOGLE_REDIRECT_URI=http://localhost:8001/auth/gmail/callback`
3. Restart the service

## Step 5: Quick Verification Checklist

Use this checklist to verify everything is correct:

- [ ] **API Gateway is running** (port 8000)
- [ ] **Gmail Connector Service is running** (port 8001)
- [ ] **`.env` file exists** in `services/api-gateway/`
- [ ] **`GOOGLE_REDIRECT_URI` is set** in `.env`
- [ ] **Redirect URI matches** what you see in `/debug/oauth` endpoint
- [ ] **Google Cloud Console has the exact URI** registered
- [ ] **No trailing slash** in the URI
- [ ] **Port number matches** the service that should receive the callback
- [ ] **Protocol matches** (http for local, https for production)
- [ ] **Services are accessible** (health checks pass)

## Step 6: Advanced Debugging

### Check Gateway Logs

When you start the OAuth flow, check the API Gateway logs for:
```
INFO: Initiating Gmail OAuth flow with redirect_uri: http://localhost:8001/auth/gmail/callback
INFO: OAuth callback received with redirect_uri: http://localhost:8001/auth/gmail/callback
```

### Check Gmail Connector Service Logs

When the callback is received, check the Gmail Connector Service logs for:
```
INFO: Processing OAuth callback with redirect_uri: http://localhost:8001/auth/gmail/callback
INFO: Exchanging authorization code for tokens with redirect_uri: http://localhost:8001/auth/gmail/callback
```

### Manual URL Inspection

1. Get the authorization URL (from API response or browser network tab)
2. Decode the URL:
   ```bash
   # Using Python
   python -c "import urllib.parse; print(urllib.parse.unquote('YOUR_ENCODED_URL'))"
   ```
3. Look for `redirect_uri=` parameter
4. Verify it matches your configuration

## Summary

The redirect URI must match **EXACTLY** in three places:
1. ✅ Your `.env` file (`GOOGLE_REDIRECT_URI`)
2. ✅ Google Cloud Console ("Authorized redirect URIs")
3. ✅ The actual OAuth authorization URL (generated by your code)

Use the `/debug/oauth` endpoint to see what your code is configured to use, then verify it matches Google Cloud Console.
