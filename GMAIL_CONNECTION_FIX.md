# Gmail Connection Fix - Step by Step Guide

This guide will help you fix the Gmail connection issues step by step.

## Prerequisites

Before starting, make sure you have:

1. ✅ All services running (API Gateway, Auth Service, Gmail Connector Service)
2. ✅ Google Cloud Console OAuth credentials configured
3. ✅ User logged in to the frontend

---

## Step 1: Verify Google Cloud Console Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Find your OAuth 2.0 Client ID
4. Click **Edit** (pencil icon)
5. Under **Authorized redirect URIs**, make sure you have:
   ```
   http://localhost:8000/auth/gmail/callback
   ```
6. **Important**: It must be exactly `/auth/gmail/callback` (not `/gmail/callback`)
7. Click **Save**

---

## Step 2: Verify Environment Variables

1. Open `services/gmail-connector-service/.env` (create it if it doesn't exist)
2. Make sure it contains:
   ```env
   GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret-here
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
   AUTH_SERVICE_URL=http://localhost:8003
   SERVICE_PORT=8001
   ```
3. Replace `your-client-id-here` and `your-client-secret-here` with your actual credentials
4. **Important**: Make sure `GOOGLE_REDIRECT_URI` matches exactly: `http://localhost:8000/auth/gmail/callback`
5. Save the file

---

## Step 3: Restart Gmail Connector Service (Important!)

**The "invalid_state" error happens because the service restarts and loses in-memory state tokens.**

### Option A: Run without Auto-Reload (Recommended for Testing)

1. **Stop** the gmail-connector-service if it's running
2. Navigate to the service directory:
   ```bash
   cd services/gmail-connector-service
   ```
3. Activate your virtual environment:

   ```bash
   # Windows
   .\venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

4. Run the service **WITHOUT** reload (so it doesn't restart):
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```
   **Note**: By default, uvicorn runs WITHOUT auto-reload. Only use `--reload` if you need it. For testing, don't use `--reload`.

### Option B: Keep Auto-Reload but Be Careful

If you need auto-reload for development:

- **Don't make any code changes** between clicking "Connect Gmail" and completing the OAuth flow
- Complete the OAuth flow within 2-3 minutes
- The state token expires after 10 minutes, so you have time

---

## Step 4: Verify Services Are Running

1. Open **3 separate terminal windows/tabs**:

   **Terminal 1 - API Gateway:**

   ```bash
   cd services/api-gateway
   # Start API Gateway (usually port 8000)
   ```

   **Terminal 2 - Auth Service:**

   ```bash
   cd services/auth-service
   # Start Auth Service (usually port 8003)
   ```

   **Terminal 3 - Gmail Connector Service:**

   ```bash
   cd services/gmail-connector-service
   # Start Gmail Connector Service WITHOUT --reload (port 8001)
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```

2. Verify all services are running:
   - API Gateway: `http://localhost:8000/health`
   - Auth Service: `http://localhost:8003/health`
   - Gmail Connector: `http://localhost:8001/health`

---

## Step 5: Test the Connection Flow

1. **Open your browser** and go to `http://localhost:5173`
2. **Login** if you haven't already
3. Navigate to **Settings** page
4. **Open the browser's Developer Console** (F12 → Console tab)
5. **Open the Terminal** where gmail-connector-service is running (to see logs)

6. **Click "Connect with Google" button**

   - You should see in the gmail-connector-service logs:
     ```
     Generating Gmail OAuth URL for authenticated user: <user_id>
     Generated state token for user <user_id>, expires at <time>, store size: 1
     ```
   - The browser should redirect to Google's OAuth consent screen

7. **Complete the OAuth flow**:

   - Select your Google account
   - Grant permissions
   - You should be redirected back to `http://localhost:5173/settings?gmail_connected=true&email=...`

8. **Check the logs** in the gmail-connector-service terminal:

   - You should see:
     ```
     Received callback with state: ...
     Verifying state token, store size: 1, state: ...
     State token verified successfully for user <user_id>
     Exchanging authorization code for tokens with redirect_uri: http://localhost:8000/auth/gmail/callback
     Storing Gmail tokens for user <user_id>, email: <email>
     Gmail tokens stored successfully for user <user_id>
     ```

9. **Check the frontend**:
   - You should see a success toast: "Gmail connected successfully: <email>"
   - The Gmail connection status should show as "Connected"

---

## Step 6: Troubleshooting Common Issues

### Issue: "invalid_state" Error

**Symptoms:**

- OAuth flow completes but you get redirected with `?gmail_error=invalid_state`
- Logs show: "State token not found in store"

**Solutions:**

1. ✅ **Most Common**: Service restarted - Run WITHOUT `--reload` flag (see Step 3). By default, uvicorn doesn't auto-reload, so just don't add the `--reload` flag.
2. ✅ Check if you took longer than 10 minutes (state token expires)
3. ✅ Make sure you're using the same service instance (not multiple instances)

### Issue: "redirect_uri_mismatch" Error

**Symptoms:**

- Error message mentions redirect URI mismatch
- OAuth fails immediately

**Solutions:**

1. ✅ Verify Google Cloud Console has: `http://localhost:8000/auth/gmail/callback`
2. ✅ Verify `.env` file has: `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback`
3. ✅ Both must match **exactly** (including `http://` vs `https://`)

### Issue: "invalid_grant" Error

**Symptoms:**

- OAuth flow fails during token exchange
- Error: "failed_to_exchange_authorization_code"

**Solutions:**

1. ✅ Authorization code expired (codes are single-use and short-lived)
   - Try the connection flow again from the beginning
2. ✅ Authorization code already used
   - Don't refresh or retry the same callback URL
   - Start a new connection flow
3. ✅ Check Google Cloud Console OAuth credentials are correct

### Issue: Status Shows "Not Connected" Even After Success

**Symptoms:**

- OAuth flow completes successfully
- Toast shows "Gmail connected successfully"
- But status still shows "Not Connected"

**Solutions:**

1. ✅ Check auth-service logs - tokens should be stored
2. ✅ Check gmail-connector-service logs - should see "Checking Gmail status for user X"
3. ✅ Refresh the page - the status should update
4. ✅ Check browser console for errors when fetching status

### Issue: "auth_service_unavailable" Error

**Symptoms:**

- Error when trying to connect or check status
- Network error in logs

**Solutions:**

1. ✅ Make sure auth-service is running on port 8003
2. ✅ Check `AUTH_SERVICE_URL` in `.env` is: `http://localhost:8003`
3. ✅ Verify auth-service is accessible: `http://localhost:8003/health`

---

## Step 7: Verify Connection Status

After successfully connecting:

1. **Check the Settings page** - should show:

   - ✅ "Connected to Gmail" with your email
   - ✅ "Active" badge
   - ✅ Connection date

2. **Check the database** (optional):

   ```bash
   # If using SQLite
   sqlite3 services/auth-service/auth.db
   .tables
   SELECT * FROM gmail_connections;
   ```

   You should see a record with your user_id and gmail_email

3. **Check the logs** when clicking "Check Status":
   - Should see: "Checking Gmail status for user <user_id>"
   - Should see: "Gmail status for user <user_id>: {'is_connected': True, ...}"

---

## Step 8: Test Disconnect

1. Click **"Disconnect"** button in Settings
2. Confirm the disconnection
3. Status should update to "Not Connected"
4. Try connecting again to verify the flow works

---

## Quick Reference: Service URLs

| Service         | URL                   | Port |
| --------------- | --------------------- | ---- |
| Frontend        | http://localhost:5173 | 5173 |
| API Gateway     | http://localhost:8000 | 8000 |
| Auth Service    | http://localhost:8003 | 8003 |
| Gmail Connector | http://localhost:8001 | 8001 |

## Quick Reference: Key Endpoints

| Endpoint               | Purpose                                |
| ---------------------- | -------------------------------------- |
| `/gmail/auth/url`      | Get OAuth authorization URL            |
| `/auth/gmail/callback` | OAuth callback (Google redirects here) |
| `/gmail/status`        | Get connection status                  |
| `/gmail/disconnect`    | Disconnect Gmail account               |

---

## Summary Checklist

Before testing, make sure:

- [ ] Google Cloud Console redirect URI: `http://localhost:8000/auth/gmail/callback`
- [ ] `.env` file has correct `GOOGLE_REDIRECT_URI`: `http://localhost:8000/auth/gmail/callback`
- [ ] `.env` file has valid `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- [ ] All services are running
- [ ] Gmail Connector Service is running **WITHOUT** auto-reload (don't use `--reload` flag)
- [ ] User is logged in to the frontend
- [ ] Browser console is open (to see errors)
- [ ] Service terminal is open (to see logs)

---

## If Still Not Working

1. **Check all logs** (API Gateway, Auth Service, Gmail Connector Service)
2. **Check browser console** for errors
3. **Verify each step** in the flow is working:

   - Can you get the auth URL? (Check API Gateway logs)
   - Does Google redirect back? (Check callback URL in browser)
   - Are tokens being stored? (Check auth-service logs)
   - Is status being fetched? (Check gmail-connector-service logs)

4. **Common mistakes:**
   - Service restarted between auth URL generation and callback
   - Redirect URI mismatch (check both Google Cloud Console and .env)
   - Wrong port numbers
   - Services not running
   - User not logged in

---

## Need More Help?

If you're still having issues:

1. Share the logs from gmail-connector-service terminal
2. Share any errors from browser console
3. Share what step is failing (Step 5, 6, 7, etc.)
