# Google OAuth App Publishing Guide

## Overview

To make your app available to **all users** (not just test users), you need to:
1. Complete the OAuth consent screen
2. Submit for Google verification (required for sensitive scopes like Gmail)
3. Publish the app

## Required Information

Before starting, prepare:

### 1. App Information
- **App name**: JobPulse AI (or your preferred name)
- **User support email**: Your email (prachicagoo@gmail.com)
- **App logo**: 120x120px PNG (optional but recommended)
- **App domain**: Your production domain (e.g., `yourapp.com`)
- **Application home page**: `https://yourapp.com`
- **Privacy policy URL**: `https://yourapp.com/privacy` (REQUIRED)
- **Terms of service URL**: `https://yourapp.com/terms` (REQUIRED)

### 2. Scopes Your App Uses

Your app requests these scopes:
- `openid` - Basic OpenID Connect
- `https://www.googleapis.com/auth/userinfo.email` - User email
- `https://www.googleapis.com/auth/userinfo.profile` - User profile
- `https://www.googleapis.com/auth/gmail.readonly` - **SENSITIVE SCOPE** (requires verification)

⚠️ **Important**: `gmail.readonly` is a **sensitive scope** that requires Google's verification process.

## Step-by-Step Publishing Process

### Step 1: Complete OAuth Consent Screen

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to: **APIs & Services** → **OAuth consent screen**

4. Fill in all required fields:

   **App information:**
   - App name: `JobPulse AI`
   - User support email: `prachicagoo@gmail.com`
   - App logo: Upload a 120x120px logo (optional)
   - App domain: Your domain (e.g., `yourapp.com`)
   - Developer contact information: `prachicagoo@gmail.com`

   **App domain:**
   - Application home page: `https://yourapp.com`
   - Authorized domains: Add your domain (e.g., `yourapp.com`)

   **Authorized redirect URIs:**
   - Make sure this is set: `http://localhost:8000/auth/google/callback` (for local dev)
   - Add production URI: `https://yourapp.com/auth/google/callback`

   **Scopes:**
   - The scopes should already be listed. Verify:
     - ✅ `openid`
     - ✅ `.../auth/userinfo.email`
     - ✅ `.../auth/userinfo.profile`
     - ✅ `.../auth/gmail.readonly` (sensitive)

### Step 2: Create Privacy Policy & Terms of Service

**REQUIRED** - Google requires these URLs for sensitive scopes.

Create these pages on your website:

1. **Privacy Policy** (`/privacy`):
   - Explain what data you collect
   - How you use Gmail data
   - How you store user data
   - Data retention policies
   - User rights

2. **Terms of Service** (`/terms`):
   - Usage terms
   - User responsibilities
   - Service limitations

**Quick Option**: Use a privacy policy generator:
- [Privacy Policy Generator](https://www.privacypolicygenerator.info/)
- [Terms of Service Generator](https://www.termsofservicegenerator.net/)

Make sure to include:
- That you access Gmail messages (read-only)
- How you use the data (job application tracking)
- That you don't share data with third parties
- How users can revoke access

### Step 3: Submit for Verification

1. In **OAuth consent screen**, scroll to bottom
2. Click **"PUBLISH APP"** button
3. You'll see a warning about sensitive scopes - click **"Continue"**
4. Fill out the verification form:

   **About your app:**
   - Describe what your app does: 
     ```
     JobPulse AI is a job application tracking dashboard that syncs with Gmail 
     to automatically identify and track job application emails. It helps users 
     organize their job search by categorizing emails and extracting application 
     details.
     ```
   
   - How does your app use Google user data?
     ```
     The app uses Gmail read-only access to:
     1. Search for job-related emails (application confirmations, interview invites, etc.)
     2. Extract email content to identify job applications
     3. Track application status and dates
     4. Provide a dashboard view of all job applications
     
     User data is stored securely and only used for the job tracking functionality.
     Users can disconnect their Gmail account at any time.
     ```

   **Scopes justification:**
   - For `gmail.readonly`:
     ```
     This scope is required to:
     1. Search Gmail for job application emails using Gmail API
     2. Read email content to extract job application details
     3. Track application status and dates
     
     We only request read-only access and never modify or send emails.
     ```

5. Submit for review

### Step 4: Wait for Verification

- **Review time**: Usually 1-7 business days
- Google may ask for additional information
- Check your email for updates

### Step 5: After Approval

Once approved:
1. Your app status will change to **"In production"**
2. Anyone can sign in (no test users needed)
3. Users will see a verified app badge

## Alternative: Use Restricted Scopes (Faster)

If you want to avoid verification, you could:
- Remove `gmail.readonly` scope
- Use IMAP instead (requires app passwords)
- Or use a different email service

But this would require code changes.

## Current Status Check

To check your current app status:
1. Go to: https://console.cloud.google.com/apis/credentials/consent
2. Look at the top - it should say "Testing" or "In production"

## Important Notes

⚠️ **Sensitive Scopes**: `gmail.readonly` requires verification. Google is strict about apps accessing Gmail.

✅ **Best Practice**: Start with test users during development, then publish when ready.

🔒 **Security**: Make sure your privacy policy accurately describes your data usage.

## Need Help?

- [Google OAuth Verification Guide](https://support.google.com/cloud/answer/9110914)
- [Sensitive Scopes Documentation](https://support.google.com/cloud/answer/10311615)
