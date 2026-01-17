# JobPulse AI - Docker-Based Job Application Tracker

A production-ready job application tracking system that syncs with Gmail to automatically track your job applications.

## 🏗️ Architecture

This project uses a microservices architecture with Docker:

- **Frontend**: React + Vite (served via nginx)
- **API Gateway**: FastAPI (routes requests to services)
- **Auth Service**: JWT-based authentication with Google OAuth
- **Gmail Connector**: Gmail API integration with sync engine
- **Database**: PostgreSQL (stores users, applications, sync state)

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Google OAuth credentials (Client ID & Secret)

### Setup

1. **Clone and navigate to the project:**
   ```bash
   cd job-tracker
   ```

2. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```

3. **Update `.env` with your credentials:**
   - Add your `GOOGLE_CLIENT_ID`
   - Add your `GOOGLE_CLIENT_SECRET`
   - Set a strong `JWT_SECRET`
   - Database credentials are pre-configured (change if needed)

4. **Start all services:**
   ```bash
   docker-compose up --build
   ```

5. **Access the application:**
   - Frontend: http://localhost:3000
   - API Gateway: http://localhost:8000

## 📁 Project Structure

```
job-tracker/
├── docker-compose.yml          # Orchestrates all services
├── .env.example                # Environment template
├── frontend/                   # React frontend
├── services/
│   ├── api-gateway/           # API routing service
│   ├── auth-service/          # Authentication service
│   └── gmail-connector/       # Gmail sync service
└── volumes/                   # Persistent data (PostgreSQL)
```

## 🔐 Key Features

- **Zero Local Dependencies**: Everything runs in Docker
- **Real-Time Sync**: Live progress tracking during Gmail sync
- **No Data Limits**: Shows ALL fetched emails (no pagination caps)
- **Account Isolation**: Switching accounts clears all previous data
- **Database-Backed**: PostgreSQL for reliable data storage
- **Incremental Sync**: Uses Gmail historyId for efficient updates
- **Two-Stage Classification**: High recall + high precision pipeline
- **Ghosted Detection**: Automatic time-based ghosted application detection
- **Production Ready**: Error handling, logging, and state management

## 🛠️ Development

### Rebuild a specific service:
```bash
docker-compose build frontend
docker-compose up frontend
```

### View logs:
```bash
docker-compose logs -f [service-name]
```

### Stop all services:
```bash
docker-compose down
```

### Clean volumes (reset state):
```bash
docker-compose down -v
```

**⚠️ Warning**: This will delete all database data!

## 📝 Important Notes

- **Every login triggers a fresh sync** - no cached data between sessions
- **Incremental syncs** - After first sync, only new emails are fetched using Gmail historyId
- **No frontend pagination limits** - all emails are displayed using virtualization
- **Sync locks prevent concurrent syncs** - locks expire after 10 minutes, auto-release on crash
- **Dashboard shows real counts** - numbers come directly from database, never estimated
- **Account switching** - Completely wipes all data for privacy
- **Email ownership validation** - Gmail email must match authenticated user email

## 🐛 Troubleshooting

- **503 Service Unavailable**: Check if gmail-connector service is running
- **Sync stuck**: Restart the gmail-connector service to release locks
- **Auth errors**: Verify Google OAuth credentials in `.env`
- **Port conflicts**: Modify ports in `docker-compose.yml`

## 📄 License

MIT
