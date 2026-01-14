# Service Verification Guide

## ✅ Services Status

All backend services have been restarted and should be running:

- **API Gateway** (port 8000) - Main entry point for all requests
- **Application Service** (port 8002) - Handles applications data
- **Auth Service** (port 8003) - Handles authentication
- **Gmail Connector Service** (port 8001) - Handles Gmail integration
- **Email Intelligence Service** (port 8004) - Handles email classification

## 🔐 Authentication Setup

### JWT Token Required

The `/metrics` and `/applications` endpoints require authentication:

1. **Login first**: You must be logged in to access protected endpoints
2. **JWT Token**: The frontend automatically includes the JWT token in requests
3. **401 Unauthorized**: If you see 401, you need to log in
4. **404 Not Found**: If you see 404, check if:
   - The route is registered in the API Gateway
   - The service is running
   - The path is correct

### How Authentication Works

1. User logs in via `/auth/login` or Google OAuth
2. Auth service returns a JWT token
3. Frontend stores the token in localStorage/sessionStorage
4. Frontend includes token in `Authorization: Bearer <token>` header
5. API Gateway validates the token using `require_auth` dependency
6. If valid, request is forwarded to backend services

## 🗄️ Database Configuration

### Application Service Database

The application-service uses SQLite by default for local development:

- **Location**: `services/application-service/app.db`
- **Configuration**: Set in `services/application-service/.env`
- **Default**: `DATABASE_URL=sqlite:///./app.db`

### Verify Database Connection

```powershell
cd services/application-service
python -c "from app.db.supabase import get_db; next(get_db()); print('✅ Database connection works')"
```

### Create Tables (if needed)

```powershell
cd services/application-service
python -c "from app.db.supabase import create_tables; create_tables(); print('✅ Tables created')"
```

## 🔍 Troubleshooting

### 1. 404 on /metrics

**Possible causes:**
- User is not authenticated (should be 401, not 404)
- Route not registered in API Gateway
- Service not running

**Solutions:**
- Log in first
- Check if API Gateway has `metrics_proxy.router` included
- Verify service is running on port 8000

### 2. 500 on /applications

**Possible causes:**
- Database connection error
- Missing tables
- Invalid database schema

**Solutions:**
- Check `services/application-service/app.db` exists
- Verify `.env` file has `DATABASE_URL` set
- Check service logs for specific error
- Create tables if needed

### 3. 401 Unauthorized

**Possible causes:**
- Not logged in
- Token expired
- Invalid token

**Solutions:**
- Log in again
- Check if token is being sent in headers
- Verify JWT secret matches between services

## 📋 Quick Verification Commands

### Check Service Health

```powershell
# API Gateway
curl http://localhost:8000/health

# Application Service
curl http://localhost:8002/health

# Auth Service
curl http://localhost:8003/health
```

### Test Metrics Endpoint (requires auth)

```powershell
# First, get a token by logging in
# Then use it:
curl -H "Authorization: Bearer <YOUR_TOKEN>" http://localhost:8000/metrics
```

### Check Database

```powershell
cd services/application-service
python -c "from app.db.supabase import engine; print('Tables:', engine.table_names())"
```

## 📝 Environment Variables

### API Gateway (.env)

```env
JWT_SECRET=your-secret-key-here
ENV=dev
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
```

### Application Service (.env)

```env
DATABASE_URL=sqlite:///./app.db
PROJECT_NAME=Application Service
```

## ✅ Next Steps

1. **Ensure you're logged in** before accessing `/metrics` or `/applications`
2. **Check service logs** if you see errors (they're in minimized PowerShell windows)
3. **Verify database exists** at `services/application-service/app.db`
4. **Start frontend** separately: `cd frontend && npm run dev`

All services should now be running with the latest fixes applied!
