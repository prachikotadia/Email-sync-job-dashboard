# Quick Setup Guide - Google OAuth & Gmail Integration

## 🚀 Quick Start (5 minutes)

### 1. Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or select existing)
3. Enable **Gmail API** and **Google+ API**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Application type: **Web application**
6. Authorized redirect URI: `http://localhost:3000/auth/callback`
7. Copy **Client ID** and **Client Secret**

### 2. Configure OAuth Consent Screen

1. Go to **OAuth consent screen**
2. Fill in app name and your email
3. Add scopes:
   - `userinfo.email`
   - `userinfo.profile`
   - `gmail.readonly`
4. Add yourself as a test user

### 3. Set Up Environment Variables

Create `.env` file in project root:

```env
# Database
DB_USER=jobpulse
DB_PASSWORD=jobpulse_password
DB_NAME=jobpulse_db

# JWT (generate with: openssl rand -hex 32)
JWT_SECRET=your-strong-random-secret-here

# Google OAuth (from Step 1)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
REDIRECT_URI=http://localhost:3000/auth/callback

# Optional
GHOSTED_DAYS=21
```

### 4. Start the Application

```bash
docker-compose up --build
```

### 5. Test Login

1. Open http://localhost:3000
2. Click "Sign in with Google"
3. Grant permissions
4. You're in! 🎉

---

## 📋 What Happens During Login

1. **User clicks "Sign in with Google"**
   - Frontend calls `/api/auth/login`
   - API Gateway proxies to Auth Service
   - Auth Service returns Google OAuth URL

2. **User authorizes on Google**
   - Google redirects to `/auth/callback?code=...`
   - Frontend extracts code and calls `/api/auth/callback`

3. **Backend processes OAuth**
   - Auth Service exchanges code for tokens
   - Stores OAuth tokens in Gmail Connector service
   - Creates JWT token for frontend

4. **Frontend receives JWT**
   - Stores JWT in localStorage
   - User is now authenticated
   - Can access Gmail sync features

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Redirect URI mismatch | Check `.env` REDIRECT_URI matches Google Console |
| Invalid client | Verify GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET |
| Access blocked | Add your email as test user in OAuth consent screen |
| Gmail not working | Ensure Gmail API is enabled and `gmail.readonly` scope is added |

---

## 📚 Full Documentation

See [GOOGLE_CLOUD_SETUP.md](./GOOGLE_CLOUD_SETUP.md) for detailed instructions.
