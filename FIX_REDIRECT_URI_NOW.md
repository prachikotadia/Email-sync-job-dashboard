# Immediate Fix for Redirect URI Mismatch

Your Google Cloud Console is correct: `http://localhost:8000/auth/gmail/callback`
Your .env file is correct: `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback`

But you're still getting the error. Here's how to fix it:

## Step 1: RESTART the Gmail Connector Service

**This is critical!** The service caches the configuration. Even if your .env file is correct, the running service might be using old config.

1. **Stop the service** (press Ctrl+C in the terminal where it's running)
2. **Start it again:**
   ```bash
   cd services/gmail-connector-service
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```

## Step 2: Check the Logs When You Try to Connect

After restarting, try connecting Gmail again and look for these log lines:

```
INFO:app.api.gmail_auth:Using redirect_uri for OAuth: 'http://localhost:8000/auth/gmail/callback' (length: 47)
INFO:app.security.oauth:Generating authorization URL with redirect_uri: 'http://localhost:8000/auth/gmail/callback'
```

If you see a DIFFERENT redirect URI in the logs, that's the problem.

## Step 3: Verify No Whitespace Issues

Make sure your .env file line looks EXACTLY like this (no spaces, no quotes):

```
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
```

NOT:
- `GOOGLE_REDIRECT_URI = http://localhost:8000/auth/gmail/callback` (spaces around =)
- `GOOGLE_REDIRECT_URI="http://localhost:8000/auth/gmail/callback"` (quotes)
- `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback ` (trailing space)

## Step 4: Try Again

After restarting the service:
1. Try connecting Gmail again
2. Check the logs to see what redirect_uri is being used
3. If it still fails, copy the EXACT redirect_uri from the logs and compare it character-by-character with Google Cloud Console

## Alternative: Verify in Google Cloud Console

1. Go to Google Cloud Console → Credentials
2. Click on your OAuth Client ID
3. Look at "Authorized redirect URIs"
4. Make sure it shows EXACTLY: `http://localhost:8000/auth/gmail/callback`
5. If there are multiple URIs, remove any wrong ones
6. Click SAVE
7. Wait 1-2 minutes for changes to propagate

## Still Not Working?

If after restarting you still get the error, share the log output that shows:
- "Using redirect_uri for OAuth: ..."
- "Generating authorization URL with redirect_uri: ..."

This will tell us exactly what redirect URI your code is using vs what Google expects.
