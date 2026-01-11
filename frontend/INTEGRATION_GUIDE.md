# Frontend Authentication Integration Guide

This guide explains how the frontend is connected to the backend authentication service.

## Overview

The frontend now uses real authentication via the API Gateway. All API requests go through the gateway at `http://localhost:8000`, which handles JWT token verification and routing to backend services.

## Setup

### 1. Environment Variables

Create a `.env` file in the `frontend/` directory:

```env
VITE_API_GATEWAY_URL=http://localhost:8000
```

Or copy from the example:
```bash
cp .env.example .env
```

### 2. Start Backend Services

Make sure the backend services are running:

1. **Auth Service** (port 8003):
   ```bash
   cd services/auth-service
   .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8003
   ```

2. **API Gateway** (port 8000):
   ```bash
   cd services/api-gateway
   .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. **Application Service** (port 8002) - if needed for full functionality

### 3. Start Frontend

```bash
cd frontend
npm install  # if not already done
npm run dev
```

The frontend will start at `http://localhost:5173` (default Vite port).

## Authentication Flow

### Registration

1. User visits the login page
2. Clicks "Register" tab
3. Enters email and password (min 8 characters)
4. Optionally selects role (viewer/editor)
5. First user automatically gets "editor" role
6. After registration, switches to login mode

### Login

1. User enters email and password
2. Frontend sends POST request to `/auth/login` via API Gateway
3. Backend validates credentials and returns:
   - `access_token` (JWT, 15 min expiry)
   - `refresh_token` (JWT, 7 days expiry)
   - `user` object (id, email, role)
4. Tokens are stored in localStorage
5. User is redirected to dashboard

### Protected Routes

All routes except `/` (login) require authentication. The `RequireAuth` guard:
- Checks if user is authenticated
- Redirects to login if not authenticated
- Allows access if authenticated or in demo mode

### Token Refresh

- Access tokens expire after 15 minutes
- Refresh tokens expire after 7 days
- Frontend automatically refreshes tokens every 10 minutes
- On 401 response, frontend attempts to refresh token
- If refresh fails, user is logged out and redirected to login

### Logout

1. User clicks "Sign Out" in sidebar or settings
2. Frontend sends POST to `/auth/logout` with refresh token
3. Backend revokes the refresh token
4. Frontend clears all tokens from localStorage
5. User is redirected to login page

## API Integration

### All Requests Go Through Gateway

All API calls are made to the API Gateway (`VITE_API_GATEWAY_URL`):

- `/auth/*` - Authentication endpoints (proxied to auth-service)
- `/applications/*` - Application management (proxied to application-service)
- `/resumes/*` - Resume management (proxied to application-service)
- `/export/*` - Data export (proxied to application-service)

### Authentication Headers

All authenticated requests automatically include:

```
Authorization: Bearer <access_token>
```

The API client (`services/api.js`) adds this header via an interceptor.

### Error Handling

- **401 Unauthorized**: Automatically attempts token refresh, then redirects to login if refresh fails
- **403 Forbidden**: Shows error message (RBAC violation)
- **500 Server Error**: Falls back to demo mode if enabled
- **Network Error**: Shows error toast notification

## File Structure

```
frontend/src/
├── context/
│   └── AuthContext.jsx      # Authentication state management
├── services/
│   ├── authService.js       # Auth API client
│   └── api.js               # Main API client with interceptors
├── pages/
│   └── Login.jsx            # Login/Register form
├── app/
│   ├── guards/
│   │   └── RequireAuth.jsx  # Route protection
│   └── router.jsx           # Route configuration
└── config/
    └── env.js               # Environment configuration
```

## Key Components

### AuthContext

Provides authentication state and methods:
- `user` - Current user object
- `isAuthenticated` - Boolean authentication status
- `isLoading` - Initial auth check status
- `login(email, password)` - Login function
- `register(email, password, role)` - Registration function
- `logout()` - Logout function

### API Client

Centralized axios instance with:
- Automatic token injection
- Token refresh on 401
- Error handling
- Request/response interceptors

### RequireAuth Guard

Protects routes by checking authentication status and redirecting unauthenticated users to login.

## Demo Mode

The app still supports demo mode for development/testing:
- Can be enabled via `DemoContext`
- Allows access without authentication
- Uses mock data instead of real API calls

To disable demo mode, ensure all environment variables are set correctly and backend services are running.

## Troubleshooting

### "Failed to fetch" errors
- Check that API Gateway is running on port 8000
- Verify `VITE_API_GATEWAY_URL` in `.env` file
- Check browser console for CORS errors

### "Unauthorized" errors after login
- Check that auth-service is running on port 8003
- Verify JWT_SECRET matches between auth-service and api-gateway
- Check browser localStorage for `auth_access_token`

### Token refresh not working
- Check network tab for refresh token request
- Verify refresh token is stored in localStorage
- Check auth-service logs for errors

### Can't register/login
- Check backend service logs
- Verify database connection (Supabase or SQLite)
- Check email format is valid
- Ensure password is at least 8 characters