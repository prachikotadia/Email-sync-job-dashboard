# Gmail Connection - Quick Start Guide

This guide provides a quick overview of the Gmail OAuth integration and how to get started.

## ⚠️ Important: Gmail OAuth Scope Requirements

**CRITICAL: Gmail Search Queries Require `gmail.readonly` Scope**

The email sync feature uses Gmail search queries (the `q` parameter) to find job-related emails. This requires the `gmail.readonly` scope, **not** `gmail.metadata`.

- ✅ **`gmail.readonly`**: Supports search queries (e.g., `is:unread OR subject:application`)
- ❌ **`gmail.metadata`**: Does NOT support search queries and will return 403 error: "Metadata scope does not support 'q' parameter"

**If you encounter a 403 error when syncing emails**, it means your Gmail connection has only the `gmail.metadata` scope. **Disconnect and reconnect your Gmail account** to get the correct `gmail.readonly` scope.

The application now automatically requests `gmail.readonly` scope for all new connections. If you have an existing connection with metadata-only scope, you must disconnect and reconnect to get the correct permissions.

## What Was Implemented

### Backend Services

1. **Gmail Connector Service** (`services/gmail-connector-service/`)
   - OAuth 2.0 flow implementation
   - Gmail API integration
   - Token management

2. **Auth Service** (`services/auth-service/`)
   - Database model for storing Gmail connections (`GmailConnection`)
   - API endpoints for token storage and retrieval
   - Connection status management

3. **API Gateway** (`services/api-gateway/`)
   - Proxy routes for Gmail endpoints
   - JWT authentication enforcement
   - Request routing

### Frontend

1. **Gmail Service** (`frontend/src/services/gmailService.js`)
   - API client for Gmail connection endpoints
   - OAuth flow initiation
   - Connection status checking

2. **Settings Page** (`frontend/src/pages/Settings.jsx`)
   - Gmail connection UI
   - Connect/Disconnect functionality
   - Connection status display
   - OAuth callback handling

## Quick Start

### 1. Set Up Google Cloud Credentials

Follow the detailed guide in [`GOOGLE_CLOUD_SETUP.md`](./GOOGLE_CLOUD_SETUP.md) to:
- Create a Google Cloud project
- Enable Gmail API
- Create OAuth 2.0 credentials
- Configure OAuth consent screen

### 2. Configure Environment Variables

Create `services/gmail-connector-service/.env`:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/gmail/callback
AUTH_SERVICE_URL=http://localhost:8003
SERVICE_PORT=8001
```

### 3. Install Dependencies

```bash
# Gmail Connector Service
cd services/gmail-connector-service
python -m venv venv
.\venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 4. Start Services

You need to start three services:

**Terminal 1 - Auth Service:**
```bash
cd services/auth-service
.\venv\Scripts\activate  # Windows
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

**Terminal 2 - Gmail Connector Service:**
```bash
cd services/gmail-connector-service
.\venv\Scripts\activate  # Windows
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 3 - API Gateway:**
```bash
cd services/api-gateway
.\venv\Scripts\activate  # Windows
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 4 - Frontend:**
```bash
cd frontend
npm run dev
```

### 5. Test Gmail Connection

1. Open `http://localhost:5173` in your browser
2. Login to your account
3. Navigate to **Settings** page
4. Find the **"Gmail Connection"** section
5. Click **"Connect with Google"**
6. You'll be redirected to Google's OAuth consent screen
7. Authorize the application
8. You'll be redirected back to Settings with a success message
9. Your Gmail connection status should now show as "Connected"

## API Endpoints

### Through API Gateway (Port 8000)

- `GET /gmail/auth/url` - Get OAuth authorization URL (requires JWT)
- `GET /gmail/callback` - OAuth callback handler (no JWT required)
- `GET /gmail/status` - Get Gmail connection status (requires JWT)
- `POST /gmail/disconnect` - Disconnect Gmail account (requires JWT)

### Direct Gmail Connector Service (Port 8001)

- `GET /health` - Health check
- `GET /auth/gmail/url` - Get OAuth URL (internal)
- `GET /auth/gmail/callback` - OAuth callback (internal)
- `GET /gmail/status` - Get connection status (internal)
- `POST /gmail/disconnect` - Disconnect (internal)

### Auth Service (Port 8003)

- `POST /api/gmail/store-tokens` - Store OAuth tokens (internal)
- `GET /api/gmail/status` - Get connection status (internal)
- `POST /api/gmail/disconnect` - Disconnect (internal)
- `GET /api/gmail/tokens` - Get tokens (internal)

## Database Schema

The `gmail_connections` table is automatically created when you start the auth-service:

```sql
CREATE TABLE gmail_connections (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) UNIQUE NOT NULL,
    tokens VARCHAR(2000) NOT NULL,  -- JSON string with encrypted OAuth tokens
    gmail_email VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    connected_at TIMESTAMP DEFAULT NOW(),
    last_synced_at TIMESTAMP,
    revoked_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

## Troubleshooting

### Common Issues

1. **"redirect_uri_mismatch"**
   - Verify `GOOGLE_REDIRECT_URI` matches exactly what's in Google Cloud Console
   - Default should be: `http://localhost:8000/gmail/callback`

2. **"invalid_client"**
   - Check `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct
   - No extra spaces or quotes

3. **"Service Unavailable"**
   - Ensure gmail-connector-service is running on port 8001
   - Check `AUTH_SERVICE_URL` is correct

4. **Connection not persisting**
   - Verify auth-service database is accessible
   - Check `gmail_connections` table exists
   - Review auth-service logs for errors

For more detailed troubleshooting, see [`GOOGLE_CLOUD_SETUP.md`](./GOOGLE_CLOUD_SETUP.md).

## Next Steps

After Gmail connection is working:
- Implement Gmail email sync functionality
- Add email parsing and job application extraction
- Create scheduled sync jobs
- Add email notification preferences

## Security Notes

- OAuth tokens are stored in the database (consider encryption for production)
- State tokens expire after 10 minutes
- All endpoints except callback require JWT authentication
- Read-only Gmail API scopes are used (no write access)