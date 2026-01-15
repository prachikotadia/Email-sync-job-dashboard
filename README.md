# Email Sync Job Dashboard

A production-grade, cross-platform Gmail email sync and job application tracking dashboard. Works seamlessly on **Windows**, **macOS**, and **Linux**.

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ ([Download](https://nodejs.org/))
- **Python** 3.8+ ([Download](https://www.python.org/downloads/))
- **Google OAuth Credentials** ([Get them here](https://console.cloud.google.com/apis/credentials))

### One-Command Setup

```bash
# Clone the repository
git clone <repository-url>
cd Email-sync-job-dashboard

# IMPORTANT: Run these commands from the PROJECT ROOT, not from frontend/
# Run setup (works on Windows, Mac, and Linux)
npm run setup
```

This will:
- ✅ Check Node.js and Python versions
- ✅ Create virtual environments for all services
- ✅ Install all dependencies
- ✅ Create `.env` file from template
- ✅ Validate your environment

### Configure Google OAuth

1. Edit `.env` file in the project root
2. Add your Google OAuth credentials:

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/gmail/callback
```

**How to get Google OAuth credentials:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable Gmail API
4. Go to **APIs & Services** → **Credentials**
5. Create **OAuth 2.0 Client ID**
6. Add authorized redirect URI: `http://localhost:8000/auth/gmail/callback`
7. Copy Client ID and Client Secret to `.env`

### Verify Setup

```bash
npm run verify
```

This checks:
- ✅ Node.js and Python are installed
- ✅ All services have virtual environments
- ✅ Dependencies are installed
- ✅ Environment variables are configured

### Start All Services

```bash
# Cross-platform script (works on Windows, Mac, Linux)
npm run dev
```

Or use platform-specific scripts:

**Windows (PowerShell):**
```powershell
.\start-all-services.ps1
```

**macOS/Linux:**
```bash
./start-all-services.sh
```

### Access the Application

- **Frontend**: http://localhost:5173
- **API Gateway**: http://localhost:8000
- **Auth Service**: http://localhost:8003
- **Gmail Connector**: http://localhost:8001
- **Application Service**: http://localhost:8002

## 📋 Platform-Specific Notes

### Windows

- ✅ All paths use cross-platform path handling
- ✅ PowerShell scripts included
- ✅ No manual path fixes needed
- ✅ Works with both CMD and PowerShell

**Common Windows Issues:**

1. **Python not found:**
   ```powershell
   # Make sure Python is in PATH
   python --version
   # If not, add Python to PATH during installation
   ```

2. **Node.js not found:**
   ```powershell
   # Install Node.js from nodejs.org
   # Make sure to check "Add to PATH" during installation
   ```

3. **Permission errors:**
   ```powershell
   # Run PowerShell as Administrator if needed
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

### macOS

- ✅ Works out of the box
- ✅ Uses `python3` automatically
- ✅ Handles path separators correctly

**Common macOS Issues:**

1. **Python 3 not found:**
   ```bash
   # Install via Homebrew
   brew install python3
   ```

2. **Permission errors:**
   ```bash
   # Make scripts executable
   chmod +x *.sh
   ```

### Linux

- ✅ Works on Ubuntu, Debian, Fedora, etc.
- ✅ Uses `python3` automatically
- ✅ Handles path separators correctly

## 🛠️ Development

### Start Individual Services

```bash
# Frontend
npm run start:frontend

# Backend services
npm run start:gateway
npm run start:auth
npm run start:gmail
npm run start:app
```

### Project Structure

```
Email-sync-job-dashboard/
├── frontend/              # React + Vite frontend
├── services/
│   ├── api-gateway/      # API Gateway (port 8000)
│   ├── auth-service/     # Authentication (port 8003)
│   ├── gmail-connector-service/  # Gmail sync (port 8001)
│   ├── application-service/      # Applications (port 8002)
│   ├── email-intelligence-service/ # Classification (port 8004)
│   └── notification-service/      # Notifications (port 8005)
├── setup.js              # Cross-platform setup script
├── verify.js             # Environment verification
├── start-all.js          # Cross-platform start script
└── .env.example          # Environment template
```

## 🔧 Configuration

### Environment Variables

All configuration is in `.env` file. See `.env.example` for template.

**Required:**
- `GOOGLE_CLIENT_ID` - Google OAuth Client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth Client Secret

**Optional (with defaults):**
- `GOOGLE_REDIRECT_URI` - OAuth redirect URI (default: http://localhost:8000/auth/gmail/callback)
- `AUTH_SERVICE_URL` - Auth service URL (default: http://localhost:8003)
- `APPLICATION_SERVICE_URL` - Application service URL (default: http://localhost:8002)
- `CORS_ORIGINS` - CORS allowed origins (default: http://localhost:5173)
- `DATABASE_URL` - Database connection string (default: SQLite)

## 🐛 Troubleshooting

### Services Won't Start

1. **Check environment:**
   ```bash
   npm run verify
   ```

2. **Reinstall dependencies:**
   ```bash
   npm run setup
   ```

3. **Check logs:**
   - Each service logs to its terminal window
   - Look for error messages in red

### OAuth Not Working

1. **Verify credentials in `.env`:**
   ```bash
   # Make sure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set
   ```

2. **Check redirect URI:**
   - Must match exactly: `http://localhost:8000/auth/gmail/callback`
   - Must be added in Google Cloud Console

3. **Clear browser cache:**
   - Sometimes OAuth tokens get cached
   - Try incognito/private window

### Database Issues

- SQLite databases are created automatically
- Paths are handled cross-platform
- If issues persist, check file permissions

### Port Already in Use

If a port is already in use:

1. **Find the process:**
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Mac/Linux
   lsof -i :8000
   ```

2. **Kill the process:**
   ```bash
   # Windows
   taskkill /PID <pid> /F
   
   # Mac/Linux
   kill -9 <pid>
   ```

## 📚 Additional Resources

- [Google OAuth Setup Guide](./GOOGLE_OAUTH_PUBLISH_GUIDE.md)
- [Testing Guide](./TESTING_GUIDE.md)
- [Architecture Documentation](./ALL_FIXES_SUMMARY.md)

## 🤝 Contributing

This project is designed for cross-platform collaboration:

1. **Windows developers:** Use PowerShell scripts or `npm run` commands
2. **Mac/Linux developers:** Use bash scripts or `npm run` commands
3. **All platforms:** Use `npm run setup` and `npm run dev` for consistency

## ✅ Cross-Platform Guarantees

- ✅ No hardcoded paths (`/Users/`, `C:\`, etc.)
- ✅ Path separators handled automatically (`/` vs `\`)
- ✅ Python version detection (`python` vs `python3`)
- ✅ Environment variable validation
- ✅ Cross-platform file permissions
- ✅ Works on Windows, macOS, and Linux

## 📝 License

MIT
