# Google Cloud Console Setup Instructions

This guide will walk you through setting up Google OAuth and Gmail API access for the Email Sync Job Dashboard.

## Prerequisites

- A Google account
- Access to Google Cloud Console (https://console.cloud.google.com)

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click the project dropdown at the top of the page
3. Click **"New Project"**
4. Enter a project name (e.g., "JobPulse Email Sync")
5. Click **"Create"**
6. Wait for the project to be created, then select it from the project dropdown

---

## Step 2: Enable Required APIs

1. In the Google Cloud Console, go to **"APIs & Services"** > **"Library"**
2. Search for and enable the following APIs:
   - **Google+ API** (for user info)
   - **Gmail API** (for email access)
3. Click **"Enable"** for each API

---

## Step 3: Create OAuth 2.0 Credentials

1. Go to **"APIs & Services"** > **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** at the top
3. Select **"OAuth client ID"**
4. If prompted, configure the OAuth consent screen first (see Step 4 below)
5. For **Application type**, select **"Web application"**
6. Enter a name (e.g., "JobPulse Web Client")
7. Under **"Authorized redirect URIs"**, add:
   ```
   http://localhost:3000/auth/callback
   ```
   > **Note:** For production, also add your production URL:
   > ```
   > https://yourdomain.com/auth/callback
   > ```
8. Click **"Create"**
9. **IMPORTANT:** Copy the **Client ID** and **Client Secret** - you'll need these for your `.env` file

---

## Step 4: Configure OAuth Consent Screen

1. Go to **"APIs & Services"** > **"OAuth consent screen"**
2. Select **"External"** (unless you have a Google Workspace account)
3. Click **"Create"**
4. Fill in the required information:
   - **App name**: JobPulse (or your preferred name)
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
5. Click **"Save and Continue"**
6. On the **Scopes** page:
   - Click **"+ ADD OR REMOVE SCOPES"**
   - Select the following scopes:
     - `.../auth/userinfo.email`
     - `.../auth/userinfo.profile`
     - `.../auth/gmail.readonly`
   - Click **"Update"**, then **"Save and Continue"**
7. On the **Test users** page (for testing):
   - Click **"+ ADD USERS"**
   - Add your Google account email
   - Click **"Add"**, then **"Save and Continue"**
8. Review and click **"Back to Dashboard"**

> **Note:** For production, you'll need to submit your app for verification if you want to use it with users outside your organization.

---

## Step 5: Configure Your Application

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` and fill in your Google OAuth credentials:
   ```env
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   REDIRECT_URI=http://localhost:3000/auth/callback
   ```

3. Generate a strong JWT secret:
   ```bash
   # On Linux/Mac:
   openssl rand -hex 32
   
   # On Windows (PowerShell):
   -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
   ```
   
   Add it to `.env`:
   ```env
   JWT_SECRET=your-generated-secret-here
   ```

---

## Step 6: Verify Configuration

1. Start your Docker containers:
   ```bash
   docker-compose up --build
   ```

2. Check service health:
   ```bash
   # API Gateway
   curl http://localhost:8000/health
   
   # Auth Service
   curl http://localhost:8001/health
   
   # Gmail Connector Service
   curl http://localhost:8002/health
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:3000
   ```

4. Click **"Sign in with Google"**
5. You should be redirected to Google's OAuth consent screen
6. After granting permissions, you'll be redirected back to the app
7. The app will now have access to your Gmail account

---

## Troubleshooting

### "Redirect URI mismatch" Error

- Ensure the redirect URI in your `.env` file exactly matches the one in Google Cloud Console
- Check for trailing slashes or protocol mismatches (http vs https)

### "Access blocked: This app's request is invalid" Error

- Make sure you've added your email as a test user in the OAuth consent screen
- Verify all required scopes are added in the consent screen configuration

### "Invalid client" Error

- Double-check your `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`
- Ensure there are no extra spaces or quotes around the values

### Gmail API Not Working

- Verify Gmail API is enabled in Google Cloud Console
- Check that `gmail.readonly` scope is included in OAuth consent screen
- Ensure OAuth tokens are being stored correctly (check database)

### Database Connection Issues

- Verify PostgreSQL is running: `docker-compose ps`
- Check database credentials in `.env`
- Ensure database container is healthy: `docker-compose logs db`

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Change `REDIRECT_URI` to your production domain
- [ ] Add production redirect URI to Google Cloud Console
- [ ] Generate a strong `JWT_SECRET` (never use the default)
- [ ] Use secure database credentials
- [ ] Enable HTTPS (required for OAuth in production)
- [ ] Submit OAuth consent screen for verification (if needed)
- [ ] Set up proper token encryption for OAuth tokens in database
- [ ] Configure proper CORS origins in API Gateway
- [ ] Set up monitoring and logging
- [ ] Review and update security settings

---

## Security Best Practices

1. **Never commit `.env` file** - It contains sensitive credentials
2. **Use environment variables** - Store secrets in your deployment platform's secret management
3. **Encrypt OAuth tokens** - In production, encrypt tokens before storing in database
4. **Rotate secrets regularly** - Change JWT_SECRET periodically
5. **Limit OAuth scopes** - Only request scopes you actually need
6. **Monitor API usage** - Set up quotas and alerts in Google Cloud Console
7. **Use HTTPS** - Always use HTTPS in production

---

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Google Cloud Console](https://console.cloud.google.com)

---

## Support

If you encounter issues:

1. Check the service logs:
   ```bash
   docker-compose logs -f auth-service
   docker-compose logs -f gmail-connector-service
   ```

2. Verify environment variables are loaded:
   ```bash
   docker-compose exec auth-service env | grep GOOGLE
   ```

3. Check database for stored tokens:
   ```bash
   docker-compose exec db psql -U jobpulse -d jobpulse_db -c "SELECT email, created_at FROM users;"
   ```
