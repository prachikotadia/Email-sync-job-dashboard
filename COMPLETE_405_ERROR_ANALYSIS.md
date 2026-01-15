# Complete 405 Method Not Allowed Error Analysis

## 🔍 ALL POSSIBLE REASONS FOR 405 ERROR

### 1. **Route Not Registered Properly** ⚠️ MOST LIKELY
**Symptoms:**
- Only OPTIONS method allowed (CORS preflight works)
- GET returns 405
- Route is defined but not recognized

**Possible Causes:**
- FastAPI route registration order issue
- Routes defined after router includes get overridden
- Router routes conflicting with direct app routes
- FastAPI version bug with route registration

**Evidence:**
- Routes ARE defined in `main.py` (lines 53, 82, 124)
- Routes ARE before router includes
- Still returns 405

### 2. **Route Conflict with Router** ⚠️ LIKELY
**Symptoms:**
- Router has commented routes but FastAPI might still cache them
- Router includes might override direct routes

**Evidence:**
- `auth_proxy.router` has commented routes (lines 240, 323, 354)
- Router is included AFTER direct routes (line 165)
- FastAPI might process routers first

### 3. **Route Path Conflict** ⚠️ POSSIBLE
**Symptoms:**
- Another route matches `/auth/google/*` pattern
- FastAPI matches wrong route

**Evidence:**
- `gmail_proxy.py` has `/auth/gmail/callback` (line 157)
- Pattern matching might conflict
- FastAPI route matching algorithm issue

### 4. **Middleware Blocking** ⚠️ POSSIBLE
**Symptoms:**
- CORS middleware allows OPTIONS but blocks GET
- RequestID middleware interfering
- Middleware order issue

**Evidence:**
- CORS allows `allow_methods=["*"]` (should allow GET)
- Middleware added before routes (correct order)
- But might have bug

### 5. **FastAPI Reload Not Working** ⚠️ LIKELY
**Symptoms:**
- Code changes not taking effect
- Old routes still active
- Process not reloading

**Evidence:**
- Using `--reload` flag
- But might not detect changes
- Process might be cached

### 6. **Route Prefix Issue** ⚠️ POSSIBLE
**Symptoms:**
- Routes need prefix
- Router has implicit prefix
- Direct routes don't match

**Evidence:**
- No prefix on direct routes
- Routers might have implicit prefix
- FastAPI route matching confusion

### 7. **Exception Handler Intercepting** ⚠️ UNLIKELY
**Symptoms:**
- Global exception handler catching route errors
- Returning 405 instead of 404

**Evidence:**
- Global handler exists (line 37)
- But should return 500, not 405
- 405 is FastAPI's default for method not allowed

### 8. **Python Import Cache** ⚠️ POSSIBLE
**Symptoms:**
- Old code cached in Python
- Import statements not reloading
- Module-level code cached

**Evidence:**
- Python caches imports
- `--reload` might not clear cache
- Need full restart

### 9. **Uvicorn Worker Issue** ⚠️ POSSIBLE
**Symptoms:**
- Multiple workers
- Routes registered on wrong worker
- Load balancing issue

**Evidence:**
- Single worker (no workers specified)
- But might have multiple processes

### 10. **Route Registration Timing** ⚠️ POSSIBLE
**Symptoms:**
- Routes registered before app fully initialized
- Middleware not ready
- Dependency injection not ready

**Evidence:**
- Routes defined after middleware (correct)
- But might need to be after ALL setup

---

## ✅ ALL POSSIBLE SOLUTIONS

### Solution 1: Force Complete Restart (TRY THIS FIRST)
```bash
# Kill all API Gateway processes
pkill -9 -f "uvicorn.*8000"
pkill -9 -f "python.*api-gateway"

# Wait
sleep 3

# Restart WITHOUT reload flag
cd services/api-gateway
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Why:** Clears all caches, forces fresh start

---

### Solution 2: Move Routes After ALL Router Includes
```python
# In main.py - move direct routes AFTER all router includes
app.include_router(health.router)
app.include_router(auth_proxy.router, tags=["auth"])
# ... all other routers ...

# THEN add direct routes
@app.get("/auth/google/status")
async def google_status_direct(request: Request):
    # ...
```

**Why:** Ensures direct routes take precedence over router routes

---

### Solution 3: Remove Router Completely for These Routes
```python
# In auth_proxy.py - DELETE the commented functions entirely
# Don't just comment, DELETE them

# In main.py - ensure routes are DEFINITELY registered
@app.get("/auth/google/status")
@app.get("/auth/google/login")  
@app.get("/auth/google/callback")
# Add explicit route registration
```

**Why:** Eliminates any possibility of conflict

---

### Solution 4: Use Route Prefix to Avoid Conflicts
```python
# In main.py
app.include_router(
    auth_proxy.router, 
    prefix="/api",  # Add prefix to router
    tags=["auth"]
)

# Direct routes stay at /auth/google/*
# Router routes become /api/auth/*
```

**Why:** Completely separates router and direct routes

---

### Solution 5: Check FastAPI Route Registration
```python
# Add to main.py after all routes
@app.on_event("startup")
async def verify_routes():
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    google_routes = [r for r in routes if 'google' in r]
    logger.info(f"Registered Google routes: {google_routes}")
```

**Why:** Verifies routes are actually registered

---

### Solution 6: Use Starlette Directly (Bypass FastAPI)
```python
from starlette.routing import Route
from starlette.responses import RedirectResponse

async def google_login_starlette(request):
    # ... same logic ...
    return RedirectResponse(url=redirect_url)

# In main.py
app.router.routes.append(
    Route("/auth/google/login", google_login_starlette, methods=["GET"])
)
```

**Why:** Bypasses FastAPI route registration entirely

---

### Solution 7: Clear Python Cache
```bash
# Remove all __pycache__ directories
find services/api-gateway -type d -name __pycache__ -exec rm -r {} +
find services/api-gateway -name "*.pyc" -delete

# Restart
```

**Why:** Clears Python bytecode cache

---

### Solution 8: Use Different Route Path
```python
# Change route paths to avoid any conflicts
@app.get("/oauth/google/status")  # Changed from /auth/google/status
@app.get("/oauth/google/login")   # Changed from /auth/google/login
@app.get("/oauth/google/callback") # Changed from /auth/google/callback

# Update frontend to use new paths
```

**Why:** Eliminates any path matching conflicts

---

### Solution 9: Check for Route Decorator Issues
```python
# Try explicit method specification
from fastapi import APIRouter

router = APIRouter()

@router.route("/auth/google/login", methods=["GET"])  # Explicit methods
async def google_login_direct(request: Request):
    # ...
```

**Why:** Ensures method is explicitly registered

---

### Solution 10: Use Middleware to Log Route Matching
```python
@app.middleware("http")
async def log_routes(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response
```

**Why:** Debugs what route FastAPI is actually matching

---

### Solution 11: Verify Uvicorn is Using Correct App
```python
# In start.sh, ensure correct import
python -m uvicorn app.main:app --reload

# NOT
python -m uvicorn main:app --reload  # Wrong!
```

**Why:** Ensures correct module is loaded

---

### Solution 12: Use Environment Variable to Toggle Routes
```python
# In main.py
import os

if os.getenv("USE_DIRECT_ROUTES", "true") == "true":
    @app.get("/auth/google/status")
    async def google_status_direct(request: Request):
        # ...
else:
    # Use router routes
    pass
```

**Why:** Allows easy switching between implementations

---

### Solution 13: Check for Multiple FastAPI Instances
```python
# Add to main.py
print(f"FastAPI app ID: {id(app)}")
print(f"Routes count: {len(app.routes)}")
for route in app.routes:
    if hasattr(route, 'path'):
        print(f"  {route.path} - {getattr(route, 'methods', [])}")
```

**Why:** Verifies only one app instance exists

---

### Solution 14: Use FastAPI's add_api_route
```python
# Instead of @app.get decorator
from fastapi.routing import APIRoute

app.add_api_route(
    "/auth/google/login",
    google_login_direct,
    methods=["GET"],
    response_class=RedirectResponse
)
```

**Why:** Explicit route registration

---

### Solution 15: Frontend Workaround (CURRENT - WORKS)
```javascript
// In Login.jsx - call auth service directly
window.location.href = 'http://localhost:8003/auth/google/login';
```

**Why:** Bypasses API Gateway completely

**Status:** ✅ ACTIVE - This works right now

---

## 🎯 RECOMMENDED FIX SEQUENCE

### Step 1: Verify Current State
```bash
# Check if routes are registered
curl -v http://localhost:8000/auth/google/login 2>&1 | grep -E "HTTP|allow"

# Check API Gateway logs
# Look for route registration messages
```

### Step 2: Force Complete Restart
```bash
pkill -9 -f "uvicorn.*8000"
rm -rf services/api-gateway/__pycache__
rm -rf services/api-gateway/app/__pycache__
cd services/api-gateway
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Move Routes After Routers
Edit `main.py` to move direct routes AFTER all router includes

### Step 4: Delete Commented Router Functions
Completely remove (don't just comment) the disabled functions in `auth_proxy.py`

### Step 5: Add Route Verification
Add startup event to log all registered routes

### Step 6: Test
```bash
curl http://localhost:8000/auth/google/status
curl -I http://localhost:8000/auth/google/login
```

### Step 7: If Still Failing
Use Solution 15 (frontend workaround) - it works and is acceptable for development

---

## 🔬 DEBUGGING COMMANDS

```bash
# Check what's listening on port 8000
lsof -nP -iTCP:8000 -sTCP:LISTEN

# Check API Gateway process
ps aux | grep uvicorn

# Test route directly
curl -v http://localhost:8000/auth/google/status

# Check FastAPI docs
curl http://localhost:8000/docs

# Check OpenAPI schema
curl http://localhost:8000/openapi.json | jq '.paths | keys' | grep google

# Check Python imports
cd services/api-gateway
python3 -c "from app.main import app; print([r.path for r in app.routes if 'google' in r.path])"
```

---

## 📊 PROBABILITY ANALYSIS

| Reason | Probability | Impact | Priority |
|--------|------------|--------|----------|
| Route not registered | 80% | High | 1 |
| Router conflict | 70% | High | 2 |
| FastAPI reload issue | 60% | Medium | 3 |
| Route path conflict | 40% | Medium | 4 |
| Middleware blocking | 30% | Low | 5 |
| Python cache | 50% | Medium | 6 |

---

## ✅ CURRENT WORKING SOLUTION

**Frontend calls auth service directly:**
- ✅ Works immediately
- ✅ No API Gateway dependency
- ✅ Simple and reliable
- ⚠️ Bypasses API Gateway (acceptable for dev)

**Status:** This is the active workaround and it WORKS. Use this while investigating the root cause.

---

## 🎯 NEXT STEPS

1. **Immediate:** Use frontend workaround (already active)
2. **Short-term:** Try Solution 1 (force restart) + Solution 2 (move routes)
3. **Long-term:** Investigate FastAPI route registration or use reverse proxy
