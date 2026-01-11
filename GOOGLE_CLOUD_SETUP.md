# Google Cloud Platform Setup Guide for Gmail OAuth

This guide walks you through setting up Google Cloud Platform (GCP) credentials to enable Gmail OAuth 2.0 integration in the Email Sync Job Dashboard.

## Prerequisites

- A Google account
- Access to [Google Cloud Console](https://console.cloud.google.com/)
- Your application's callback URL ready (default: `http://localhost:8000/auth/gmail/callback`)

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top of the page
3. Click **"New Project"**
4. Enter a project name (e.g., "Email Sync Job Dashboard")
5. Optionally, select an organization
6. Click **"Create"**
7. Wait for the project to be created, then select it from the dropdown

## Step 2: Enable Gmail API

1. In the Google Cloud Console, navigate to **"APIs & Services"** > **"Library"**
2. Search for **"Gmail API"**
3. Click on **"Gmail API"** from the results
4. Click **"Enable"**
5. Wait for the API to be enabled (this may take a minute)

## Step 3: Configure OAuth Consent Screen

1. Navigate to **"APIs & Services"** > **"OAuth consent screen"**
2. Choose **"External"** user type (unless you have a Google Workspace account, then use "Internal")
3. Click **"Create"**

### Fill in the required information:

- **App name**: `Email Sync Job Dashboard` (or your preferred name)
- **User support email**: Your email address
- **Developer contact information**: Your email address
- Click **"Save and Continue"**

### Scopes (Step 2):

1. Click **"Add or Remove Scopes"**
2. Search for and select the following scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` (View your emails messages and settings)
   - `https://www.googleapis.com/auth/gmail.metadata` (View your email message metadata such as labels and headers, but not the email body)
3. Click **"Update"**
4. Click **"Save and Continue"**

### Test users (Step 3):

1. If your app is in "Testing" mode, you need to add test users
2. Click **"Add Users"**
3. Add your Google account email address (the one you'll use to connect Gmail)
4. Click **"Add"**
5. Click **"Save and Continue"**

### Summary (Step 4):

1. Review your configuration
2. Click **"Back to Dashboard"**

## Step 4: Create OAuth 2.0 Credentials

1. Navigate to **"APIs & Services"** > **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** at the top
3. Select **"OAuth client ID"**

### If prompted to configure consent screen:
- Click **"Configure Consent Screen"** and follow Step 3 above, then return here

### Create OAuth Client:

1. Select **"Web application"** as the application type
2. Enter a **name** (e.g., "Email Sync Job Dashboard - Gmail Connector")
3. Under **"Authorized redirect URIs"**, click **"+ ADD URI"**
4. Add the following redirect URIs (one per line):
   ```
   http://localhost:8000/auth/gmail/callback
   http://localhost:8001/auth/gmail/callback
   ```
   
   **Note**: For production, add your production callback URL:
   ```
   https://yourdomain.com/auth/gmail/callback
   ```

5. Click **"Create"**

### Save Your Credentials:

6. A dialog will appear with your **Client ID** and **Client Secret**
7. **IMPORTANT**: Copy both values immediately - you won't be able to see the Client Secret again!
8. Click **"OK"**

## Step 5: Configure Your Application

### For Local Development:

1. Open `services/gmail-connector-service/.env` (create it if it doesn't exist)
2. Add the following environment variables:

```env
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here

# OAuth Redirect URI (must match one of the URIs you configured in Google Cloud)
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback

# Auth Service URL (for storing tokens)
AUTH_SERVICE_URL=http://localhost:8003

# Service Configuration
SERVICE_NAME=gmail-connector-service
SERVICE_PORT=8001
```

3. Replace `your-client-id-here` and `your-client-secret-here` with your actual credentials
4. Save the file

### For Production:

1. Set the same environment variables in your production environment
2. Make sure `GOOGLE_REDIRECT_URI` matches your production callback URL
3. Ensure the redirect URI is added to your OAuth client in Google Cloud Console

## Step 6: Verify Configuration

1. Start your services:
   ```bash
   # Terminal 1 - Auth Service
   cd services/auth-service
   .\venv\Scripts\activate  # Windows
   # or: source venv/bin/activate  # Linux/Mac
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload

   # Terminal 2 - Gmail Connector Service
   cd services/gmail-connector-service
   .\venv\Scripts\activate  # Windows
   # or: source venv/bin/activate  # Linux/Mac
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

   # Terminal 3 - API Gateway
   cd services/api-gateway
   .\venv\Scripts\activate  # Windows
   # or: source venv/bin/activate  # Linux/Mac
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Check service health:
   ```bash
   curl http://localhost:8001/health
   # Should return: {"status":"healthy","service":"gmail-connector-service"}
   ```

3. Test Gmail connection in the frontend:
   - Open `http://localhost:5173`
   - Login to your account
   - Go to Settings
   - Click "Connect with Google" under Gmail Connection
   - You should be redirected to Google's OAuth consent screen
   - After authorizing, you should be redirected back to Settings with a success message

## Troubleshooting

### Error: "redirect_uri_mismatch"

- **Cause**: The redirect URI in your `.env` file doesn't match what's configured in Google Cloud Console
- **Solution**: 
  1. Verify `GOOGLE_REDIRECT_URI` in your `.env` file
  2. Check the "Authorized redirect URIs" in Google Cloud Console
  3. Make sure they match exactly (including `http://` vs `https://`, port numbers, trailing slashes)

### Error: "invalid_client"

- **Cause**: Incorrect Client ID or Client Secret
- **Solution**:
  1. Double-check your `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`
  2. Make sure there are no extra spaces or quotes
  3. Regenerate credentials in Google Cloud Console if needed

### Error: "access_denied" or OAuth consent screen shows error

- **Cause**: 
  - App is in "Testing" mode and your account is not added as a test user
  - Required scopes are not configured
- **Solution**:
  1. Go to OAuth consent screen in Google Cloud Console
  2. Add your email as a test user (under "Test users")
  3. Verify required scopes are added (gmail.readonly, gmail.metadata)

### Error: "Service Unavailable" when connecting Gmail

- **Cause**: Gmail connector service is not running or not reachable
- **Solution**:
  1. Check if gmail-connector-service is running on port 8001
  2. Verify `AUTH_SERVICE_URL` is correct in gmail-connector-service `.env`
  3. Check API Gateway configuration for Gmail service URL

### Gmail connection works but tokens are not stored

- **Cause**: Auth service database issue or API endpoint problem
- **Solution**:
  1. Verify auth-service is running and accessible
  2. Check database connection in auth-service
  3. Verify `gmail_connections` table exists (check logs for migration messages)
  4. Check auth-service logs for errors

## Security Best Practices

1. **Never commit credentials to Git**:
   - Add `.env` files to `.gitignore`
   - Use environment variables or secret management in production

2. **Use separate credentials for development and production**:
   - Create separate OAuth clients in Google Cloud Console
   - Use different Client IDs and Secrets for each environment

3. **Restrict redirect URIs**:
   - Only add the exact URIs you need
   - Use HTTPS in production (never HTTP)

4. **Regularly rotate secrets**:
   - Rotate Client Secrets periodically
   - Update environment variables when secrets change

5. **Monitor API usage**:
   - Check Google Cloud Console for API usage and quotas
   - Set up alerts for unusual activity

## Production Deployment Checklist

- [ ] Create a new OAuth client for production
- [ ] Add production redirect URI to OAuth client
- [ ] Set `GOOGLE_REDIRECT_URI` to production URL
- [ ] Verify Gmail API is enabled in production project
- [ ] Submit OAuth consent screen for verification (if needed)
- [ ] Configure environment variables securely (use secrets manager)
- [ ] Test Gmail connection in production environment
- [ ] Set up monitoring for OAuth errors
- [ ] Configure rate limiting if needed

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth 2.0 Scopes for Gmail API](https://developers.google.com/gmail/api/auth/scopes)
- [Google Cloud Console](https://console.cloud.google.com/)

## Support

If you encounter issues not covered in this guide:
1. Check the service logs for detailed error messages
2. Review Google Cloud Console for API quotas and errors
3. Verify all environment variables are set correctly
4. Ensure all services are running and accessible