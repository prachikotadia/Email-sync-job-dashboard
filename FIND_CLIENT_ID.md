# How to Find Your Google OAuth Client ID

## Quick Method: Direct Link

1. Go to: https://console.cloud.google.com/apis/credentials
2. Look for **OAuth 2.0 Client IDs** section
3. Find the client with ID: `100820242078-20elejiluhdb4j9s1gdih1ug89hlumkf`
4. Click on it to view/edit

## Step-by-Step Navigation

### Method 1: From Google Cloud Console Home

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/

2. **Select Your Project**
   - Click the project dropdown at the top
   - Select the project that contains your OAuth credentials
   - (If you're not sure which project, try each one until you find the Client ID)

3. **Navigate to Credentials**
   - Left sidebar → **APIs & Services** → **Credentials**
   - Or direct link: https://console.cloud.google.com/apis/credentials

4. **Find Your OAuth Client**
   - Scroll to **OAuth 2.0 Client IDs** section
   - Look for Client ID: `100820242078-20elejiluhdb4j9s1gdih1ug89hlumkf`
   - The name might be something like "Web client" or "OAuth client"

5. **Click on the Client ID** to view/edit:
   - Client ID (this is what you're looking for)
   - Client secret
   - Authorized redirect URIs
   - Authorized JavaScript origins

### Method 2: Search by Client ID

1. Go to: https://console.cloud.google.com/apis/credentials
2. Use browser search (Ctrl+F / Cmd+F)
3. Search for: `100820242078-20elejiluhdb4j9s1gdih1ug89hlumkf`
4. It should highlight the matching client

### Method 3: Check All Projects

If you can't find it in the current project:

1. **List all projects:**
   - Click project dropdown at top
   - Click "All" or browse through projects

2. **For each project:**
   - Go to: APIs & Services → Credentials
   - Check OAuth 2.0 Client IDs section
   - Look for the Client ID

## What You'll See

When you click on the Client ID, you'll see:

```
OAuth 2.0 Client ID
Name: Web client (or your custom name)
Client ID: 100820242078-20elejiluhdb4j9s1gdih1ug89hlumkf
Client secret: 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 (hidden, click to reveal)

Authorized JavaScript origins:
- http://localhost:5173

Authorized redirect URIs:
- http://localhost:8000/auth/google/callback
```

## Related Settings

From the same page, you can also access:

1. **OAuth Consent Screen** (link at top)
   - Configure app name, scopes, test users
   - This is where you publish the app

2. **Edit Settings**
   - Change redirect URIs
   - Update authorized origins
   - Regenerate client secret (if needed)

## Troubleshooting

### Can't Find the Client ID?

1. **Check you're in the right project**
   - The Client ID belongs to a specific Google Cloud project
   - Make sure you're looking in the correct project

2. **Check you have permissions**
   - You need "Owner" or "Editor" role to view credentials
   - Contact project owner if you don't have access

3. **Check if it was deleted**
   - If you can't find it, it might have been deleted
   - You'll need to create a new OAuth client

### Need to Create a New Client?

If you can't find the existing one:

1. Go to: https://console.cloud.google.com/apis/credentials
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. Choose **Web application**
4. Add authorized redirect URIs:
   - `http://localhost:8000/auth/google/callback`
5. Click **CREATE**
6. Copy the new Client ID and Client Secret
7. Update your `.env` files

## Quick Links

- **Credentials page**: https://console.cloud.google.com/apis/credentials
- **OAuth consent screen**: https://console.cloud.google.com/apis/credentials/consent
- **All projects**: https://console.cloud.google.com/home/dashboard
