# Google Login Setup Guide

## Error: redirect_uri_mismatch

If you're getting "Error 400: redirect_uri_mismatch" when clicking "Continue with Google", you need to add the redirect URI to Google Cloud Console.

## Step-by-Step Fix

### 1. Check Current Redirect URI

The redirect URI being used is: **`http://localhost:8000/auth/google/callback`**

You can verify this by checking the auth-service logs when you click "Continue with Google". Look for:
```
=== GOOGLE LOGIN OAUTH DEBUG ===
Redirect URI being used: 'http://localhost:8000/auth/google/callback'
```

### 2. Add Redirect URI to Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Click on your **OAuth 2.0 Client ID** (the one you're using)
4. Under **"Authorized redirect URIs"**, click **"+ ADD URI"**
5. Add exactly this URI (copy-paste to avoid typos):
   ```
   http://localhost:8000/auth/google/callback
   ```
6. Click **"Save"**

### 3. Important Notes

- **No trailing slash**: Make sure there's NO trailing slash at the end
- **Exact match**: The URI must match EXACTLY (character-for-character)
- **Case sensitive**: `localhost` must be lowercase
- **Port number**: Must be `8000` (API Gateway port)

### 4. Multiple Redirect URIs

You can have multiple redirect URIs registered. Your Google Cloud Console should have:
- `http://localhost:8000/auth/gmail/callback` (for Gmail connection)
- `http://localhost:8000/auth/google/callback` (for Google login) ← **ADD THIS ONE**

### 5. Verify Configuration

After adding the redirect URI:

1. Wait a few seconds for Google to update
2. Try "Continue with Google" again
3. Check auth-service logs to confirm the redirect URI being used

### 6. Common Issues

**Issue**: Still getting redirect_uri_mismatch after adding URI
- **Solution**: Make sure you saved the changes in Google Cloud Console
- **Solution**: Wait 1-2 minutes for changes to propagate
- **Solution**: Check for typos (extra spaces, wrong port, trailing slash)

**Issue**: Different redirect URI in logs
- **Solution**: Check your `services/auth-service/.env` file
- **Solution**: Make sure `GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback`
- **Solution**: Restart auth-service after changing .env

## Current Configuration

Based on your setup:
- **Redirect URI**: `http://localhost:8000/auth/google/callback`
- **Client ID**: `855541696108-cr64n7g54i3fd67qqhl96qefak049jnj.apps.googleusercontent.com`
- **Service**: auth-service (port 8003)
- **Gateway**: API Gateway (port 8000)

## Testing

After adding the redirect URI:

1. Click "Continue with Google" on the login page
2. You should be redirected to Google's consent screen
3. After granting permissions, you'll be redirected back
4. Your account will be created (if new) or you'll be logged in
5. Gmail will be automatically connected

## Troubleshooting

If you still have issues, check:

1. **Auth-service logs**: Look for the exact redirect URI being used
2. **Google Cloud Console**: Verify the URI is saved correctly
3. **.env file**: Make sure `GOOGLE_REDIRECT_URI` is correct
4. **Service status**: Ensure auth-service and API Gateway are running
