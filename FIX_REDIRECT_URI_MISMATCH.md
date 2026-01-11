# Fix Redirect URI Mismatch Error

This error means the redirect URI in Google Cloud Console doesn't match what your code is using.

## Quick Fix Steps

### Step 1: Check Your Code Configuration

The code is configured to use:

```
http://localhost:8000/auth/gmail/callback
```

This is set in `services/gmail-connector-service/app/config.py` (line 11) and should also be in your `.env` file.

### Step 2: Verify Your .env File

1. Open `services/gmail-connector-service/.env`
2. Make sure it has this line (exactly as shown):
   ```env
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
   ```
3. **Important checks:**

   - ✅ Must be `http://` not `https://`
   - ✅ Must be port `8000` (API Gateway port)
   - ✅ Must be `/auth/gmail/callback` (not `/gmail/callback`)
   - ✅ No trailing slash
   - ✅ No extra spaces or quotes

4. Save the file
5. **Restart the gmail-connector-service** so it picks up the .env changes

### Step 3: Update Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Find your **OAuth 2.0 Client ID**
4. Click the **Edit** button (pencil icon) next to your OAuth client
5. Scroll down to **Authorized redirect URIs**
6. **Remove any incorrect URIs** like:
   - `http://localhost:8000/gmail/callback` ❌ (wrong - missing `/auth`)
   - `http://localhost:8001/auth/gmail/callback` ❌ (wrong port)
7. **Add the correct URI:**
   ```
   http://localhost:8000/auth/gmail/callback
   ```
8. Click **+ ADD URI** if needed
9. Type it exactly: `http://localhost:8000/auth/gmail/callback`
10. Click **SAVE**

### Step 4: Verify Both Match

**Code (from .env):**

```
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
```

**Google Cloud Console:**

```
http://localhost:8000/auth/gmail/callback
```

They must match **exactly** - character for character!

### Step 5: Test Again

1. **Restart the gmail-connector-service** (if you changed .env)
2. Try connecting Gmail again
3. The redirect URI mismatch error should be gone

---

## Common Mistakes

❌ **Wrong:**

- `https://localhost:8000/auth/gmail/callback` (using https)
- `http://localhost:8000/gmail/callback` (missing `/auth`)
- `http://localhost:8001/auth/gmail/callback` (wrong port)
- `http://localhost:8000/auth/gmail/callback/` (trailing slash)

✅ **Correct:**

- `http://localhost:8000/auth/gmail/callback`

---

## Why Port 8000?

The redirect URI uses port 8000 because:

- Port 8000 = API Gateway (where Google redirects to)
- API Gateway then forwards to gmail-connector-service (port 8001)
- This is the correct flow: Google → API Gateway (8000) → Gmail Connector Service (8001)

---

## Still Getting the Error?

1. **Double-check both places match exactly:**

   - Google Cloud Console
   - `.env` file

2. **Clear browser cache** - Sometimes browsers cache OAuth redirects

3. **Try in an incognito/private window** to avoid cached redirects

4. **Check the actual error in logs:**

   - Look at gmail-connector-service logs
   - The error message should tell you what URI it's expecting vs what it received

5. **Wait a few minutes** - Google Cloud Console changes can take 1-2 minutes to propagate
