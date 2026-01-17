# JobPulse AI - Quick Start Guide

## 🚀 Getting Started

### 1. Prerequisites
- Docker Desktop (macOS/Windows)
- Google OAuth credentials (Client ID & Secret)

### 2. Setup

```bash
# Run setup script (creates .env file)
./setup.sh

# Or manually create .env from .env.example
cp .env.example .env
```

### 3. Configure Google OAuth

Edit `.env` and add your credentials:
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
REDIRECT_URI=http://localhost:8001/auth/callback
```

### 4. Start Services

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

### 5. Access Application

- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:8000
- **Auth Service**: http://localhost:8001
- **Gmail Connector**: http://localhost:8002

## 📋 Service Endpoints

### API Gateway (http://localhost:8000/api)

- `GET /api/auth/login` - Initiate OAuth
- `POST /api/auth/callback` - Handle OAuth callback
- `GET /api/auth/me` - Get current user
- `POST /api/auth/logout` - Logout and clear data
- `GET /api/gmail/status` - Gmail connection status
- `POST /api/gmail/sync/start` - Start sync
- `GET /api/gmail/sync/progress/{job_id}` - Get sync progress
- `GET /api/gmail/applications` - Get all applications (NO pagination)
- `GET /api/gmail/stats` - Get dashboard statistics

## 🛠️ Development

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f frontend
docker-compose logs -f api-gateway
docker-compose logs -f auth-service
docker-compose logs -f gmail-connector
```

### Rebuild Service
```bash
docker-compose build frontend
docker-compose up frontend
```

### Stop Services
```bash
docker-compose down
```

### Clean Everything (Reset State)
```bash
docker-compose down -v
```

## 🔍 Troubleshooting

### Port Already in Use
Modify ports in `docker-compose.yml`:
```yaml
ports:
  - "3001:80"  # Change 3000 to 3001
```

### Gmail Service 503
- Check if gmail-connector is running: `docker-compose ps`
- Check logs: `docker-compose logs gmail-connector`
- Restart service: `docker-compose restart gmail-connector`

### Sync Stuck
- Restart gmail-connector to release locks:
  ```bash
  docker-compose restart gmail-connector
  ```

### Auth Errors
- Verify Google OAuth credentials in `.env`
- Check redirect URI matches Google Console settings
- Check auth-service logs: `docker-compose logs auth-service`

## 📁 Project Structure

```
job-tracker/
├── docker-compose.yml       # Service orchestration
├── .env                     # Environment variables (create from .env.example)
├── frontend/                # React frontend
├── services/
│   ├── api-gateway/        # API routing
│   ├── auth-service/       # Authentication
│   └── gmail-connector/    # Gmail sync
└── volumes/                 # Persistent data
```

## ✅ Key Features

- ✅ **Zero Local Dependencies** - Everything runs in Docker
- ✅ **No Pagination Limits** - Shows ALL fetched emails
- ✅ **Real-Time Sync** - Live progress tracking
- ✅ **Account Isolation** - Switching accounts clears all data
- ✅ **Production Ready** - Error handling, logging, state management

## 📚 Documentation

- See `README.md` for detailed documentation
- See `REQUIREMENTS.md` for strict requirements checklist
