# Google OAuth Collaboration Setup

## Option 1: Share the Same Client ID (Recommended for Collaboration)

If you're working together, you can both use the same Client ID. This is simpler and works well for:
- Shared development
- Testing together
- Same production app

### Steps for Your Friend (Client ID Owner)

1. **Add you to the Google Cloud Project:**
   - Go to: https://console.cloud.google.com/iam-admin/iam
   - Click **+ GRANT ACCESS**
   - Add your email: `prachicagoo@gmail.com`
   - Role: **Owner** or **Editor** (Editor is enough for most tasks)
   - Click **SAVE**

2. **Add you as a Test User:**
   - Go to: https://console.cloud.google.com/apis/credentials/consent
   - Scroll to **Test users** section
   - Click **+ ADD USERS**
   - Add: `prachicagoo@gmail.com`
   - Click **ADD**

### What You Can Do After Being Added

Once your friend adds you:
- ✅ View and edit OAuth settings
- ✅ Add/remove test users
- ✅ Update redirect URIs
- ✅ Submit for verification
- ✅ Use the same Client ID in your local setup

### Your Local Setup (No Changes Needed)

You can keep using the same Client ID:
```env
GOOGLE_CLIENT_ID=100820242078-20elejiluhdb4j9s1gdih1ug89hlumkf
GOOGLE_CLIENT_SECRET=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
```

**Benefits:**
- Same app for both of you
- Shared test users
- One verification process
- Simpler setup

---

## Option 2: Create Your Own Client ID

If you want separate Client IDs (for independent development or different projects):

### Steps to Create Your Own

1. **Create a Google Cloud Project:**
   - Go to: https://console.cloud.google.com/
   - Click **+ CREATE PROJECT**
   - Name: `JobPulse AI` (or your choice)
   - Click **CREATE**

2. **Enable Gmail API:**
   - Go to: https://console.cloud.google.com/apis/library
   - Search for "Gmail API"
   - Click **ENABLE**

3. **Create OAuth Client:**
   - Go to: https://console.cloud.google.com/apis/credentials
   - Click **+ CREATE CREDENTIALS** → **OAuth client ID**
   - If prompted, configure OAuth consent screen first:
     - User type: **External** (or Internal if using Google Workspace)
     - App name: `JobPulse AI`
     - User support email: `prachicagoo@gmail.com`
     - Developer contact: `prachicagoo@gmail.com`
     - Click **SAVE AND CONTINUE**
     - Scopes: Add these:
       - `openid`
       - `.../auth/userinfo.email`
       - `.../auth/userinfo.profile`
       - `.../auth/gmail.readonly`
     - Click **SAVE AND CONTINUE**
     - Test users: Add `prachicagoo@gmail.com`
     - Click **SAVE AND CONTINUE**
     - Click **BACK TO DASHBOARD**
   
4. **Create OAuth Client ID:**
   - Application type: **Web application**
   - Name: `Web client` (or your choice)
   - Authorized redirect URIs:
     - `http://localhost:8000/auth/google/callback`
     - (Add production URI when ready)
   - Click **CREATE**
   - **Copy the Client ID and Client Secret**

5. **Update Your .env Files:**
   
   **services/auth-service/.env:**
   ```env
   GOOGLE_CLIENT_ID=your_new_client_id_here
   GOOGLE_CLIENT_SECRET=your_new_client_secret_here
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   ```
   
   **services/api-gateway/.env:**
   ```env
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   ```

6. **Restart Services:**
   ```bash
   ./start-all-services.sh
   ```

**Benefits:**
- Independent development
- Your own test users
- Separate verification process
- More control

**Drawbacks:**
- More setup work
- Separate verification needed
- Two different apps

---

## Recommendation

### For Collaboration: Use Option 1 (Shared Client ID)

**Why:**
- ✅ Simpler setup
- ✅ One verification process
- ✅ Shared test users
- ✅ Same app experience
- ✅ Easier to manage

**Just ask your friend to:**
1. Add you to the Google Cloud project (IAM)
2. Add you as a test user (OAuth consent screen)

Then you can both use the same Client ID!

### For Independent Work: Use Option 2 (Separate Client ID)

**When to choose this:**
- You're working on different features
- You want separate test environments
- You're deploying to different domains
- You want independent control

---

## Quick Checklist

### If Using Shared Client ID:
- [ ] Friend adds you to Google Cloud project (IAM)
- [ ] Friend adds you as test user
- [ ] You use the same Client ID in your .env
- [ ] Both can sign in and test

### If Creating Your Own:
- [ ] Create Google Cloud project
- [ ] Enable Gmail API
- [ ] Configure OAuth consent screen
- [ ] Create OAuth client
- [ ] Update .env files
- [ ] Restart services
- [ ] Add yourself as test user

---

## Security Note

**Important:** Never commit Client Secrets to Git!

Make sure `.env` files are in `.gitignore`:
```
services/*/.env
.env
*.env
```

Your `.env` files should already be ignored, but double-check!
