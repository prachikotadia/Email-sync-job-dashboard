# Quick Start Guide

## ⚠️ IMPORTANT: Run Commands from Project Root

All `npm run` commands must be executed from the **project root directory**, NOT from `frontend/` or any service directory.

```bash
# ✅ CORRECT - From project root
cd Email-sync-job-dashboard
npm run setup

# ❌ WRONG - From frontend directory
cd frontend
npm run setup  # This will fail!
```

## 🚀 Setup Steps

### Step 1: Navigate to Project Root
```bash
cd Email-sync-job-dashboard
```

### Step 2: Run Setup
```bash
npm run setup
```

This will:
- ✅ Check Node.js and Python versions
- ✅ Create virtual environments for all services
- ✅ Install all dependencies
- ✅ Create `.env` file from template

### Step 3: Configure Google OAuth

Edit `.env` file in the project root:
```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

### Step 4: Verify Setup
```bash
npm run verify
```

### Step 5: Start All Services
```bash
npm run dev
```

This starts all backend services and the frontend.

## 📍 Directory Structure

```
Email-sync-job-dashboard/          ← Run npm commands HERE
├── setup.js                       ← Root-level scripts
├── verify.js
├── start-all.js
├── package.json                   ← Root package.json
├── .env                           ← Root .env file
├── frontend/                       ← Frontend code
│   └── package.json               ← Frontend has its own package.json
└── services/                      ← Backend services
    ├── api-gateway/
    ├── auth-service/
    └── ...
```

## 🔍 Troubleshooting

### "Missing script: setup"
**Problem**: You're running the command from the wrong directory.

**Solution**: 
```bash
# Make sure you're in the project root
pwd  # Should show: .../Email-sync-job-dashboard

# If you're in frontend/, go back:
cd ..

# Then run:
npm run setup
```

### Frontend Port Already in Use
If port 5173 is in use, Vite will automatically use the next available port (5174, 5175, etc.). This is normal and fine - just use the port shown in the terminal.

### Python 3.13 Build Issues
If you encounter build errors with Python 3.13, consider using Python 3.11 or 3.12:
```bash
python3.11 -m venv services/application-service/venv
```

## 📚 More Information

- See `README.md` for detailed documentation
- See `CROSS_PLATFORM_SETUP.md` for technical details
