# API Gateway Route 405 Error - Solutions

## Problem
The API Gateway is returning `405 Method Not Allowed` for `/auth/google/*` routes even though they are defined.

## Root Cause
FastAPI router registration issue - routes defined in `auth_proxy.router` are not being recognized properly, causing FastAPI to only allow OPTIONS (CORS preflight) but not GET requests.

## Solutions Implemented

### ✅ Solution 1: Direct Routes in main.py (Current)
- Added direct route definitions in `app/main.py` BEFORE router includes
- Routes: `/auth/google/status`, `/auth/google/login`, `/auth/google/callback`
- **Status**: Routes added but may need full restart to take effect

### ✅ Solution 2: Frontend Workaround (Active)
- Updated `frontend/src/pages/Login.jsx` to call auth service directly
- Falls back to `http://localhost:8003/auth/google/*` if API Gateway fails
- **Status**: ACTIVE - This is the current working solution

### ✅ Solution 3: Disabled Router Routes
- Commented out duplicate routes in `app/routes/auth_proxy.py`
- Prevents route conflicts
- **Status**: Done

## All Possible Solutions

### Option A: Use Auth Service Directly (CURRENT WORKAROUND)
**Pros:**
- Works immediately
- No API Gateway dependency for OAuth
- Simple and reliable

**Cons:**
- Bypasses API Gateway
- Frontend needs to know auth service URL
- Not ideal for production

**Implementation:**
```javascript
// In frontend
window.location.href = 'http://localhost:8003/auth/google/login';
```

### Option B: Fix API Gateway Routes (RECOMMENDED FOR PRODUCTION)
**Steps:**
1. Ensure direct routes in `main.py` are BEFORE router includes
2. Comment out router routes in `auth_proxy.py` (already done)
3. Force full restart: `pkill -9 -f "uvicorn.*8000" && ./start.sh`
4. Verify routes: `curl http://localhost:8000/auth/google/status`

**If still not working:**
- Check FastAPI route registration order
- Verify no middleware is blocking routes
- Check for route prefix conflicts

### Option C: Use Nginx/Reverse Proxy
**Setup:**
```nginx
location /auth/google/ {
    proxy_pass http://localhost:8003;
}
```
**Pros:**
- Clean separation
- Production-ready
- Handles routing properly

**Cons:**
- Requires Nginx setup
- Additional infrastructure

### Option D: Fix Router Registration
**Possible fixes:**
1. Check if router needs a prefix: `app.include_router(auth_proxy.router, prefix="/api")`
2. Verify router is imported correctly
3. Check for circular imports
4. Ensure routes are registered in correct order

### Option E: Use FastAPI Route Override
```python
# In main.py, after router includes
app.router.routes = [r for r in app.router.routes if not r.path.startswith("/auth/google")] + direct_routes
```

## Current Status
- ✅ Frontend workaround: ACTIVE (calling auth service directly)
- ⚠️ API Gateway routes: Added but may need full restart
- ✅ Router conflicts: Resolved (routes commented out)

## Testing
```bash
# Test auth service directly (should work)
curl http://localhost:8003/auth/google/status

# Test API Gateway (may still return 405)
curl http://localhost:8000/auth/google/status

# Test login redirect
curl -I http://localhost:8000/auth/google/login
```

## Next Steps
1. **Immediate**: Frontend workaround is active - app should work
2. **Short-term**: Force full API Gateway restart and test routes
3. **Long-term**: Investigate FastAPI router registration issue or use reverse proxy

## Why This Happened
FastAPI route registration can be finicky when:
- Routes are defined in routers AND directly in app
- Middleware order affects route matching
- CORS preflight (OPTIONS) works but actual method (GET) doesn't
- Route prefixes or conflicts exist

The frontend workaround ensures the app works while we investigate the root cause.
