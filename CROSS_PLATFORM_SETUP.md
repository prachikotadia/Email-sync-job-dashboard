# Cross-Platform Setup Guide

This document describes the cross-platform compatibility improvements made to the Email Sync Job Dashboard project.

## ✅ What Was Fixed

### 1. **Path Handling**
- ❌ **Before**: Hardcoded paths like `"uploads/resumes"`, `"sqlite:///./app.db"`
- ✅ **After**: Cross-platform paths using `pathlib.Path` and `os.path.join()`
- **Files Fixed**:
  - `services/application-service/app/api/resumes.py` - Uses `pathlib.Path` for uploads
  - `services/application-service/app/config.py` - Absolute database paths
  - `services/gmail-connector-service/app/config.py` - Absolute database paths
  - `services/auth-service/app/config.py` - Absolute database paths

### 2. **Python Version Detection**
- ❌ **Before**: Scripts assumed `python3` (Mac/Linux) or `python` (Windows)
- ✅ **After**: Automatic detection of available Python command
- **Files Created**:
  - `setup.js` - Detects `python3` or `python` automatically
  - `verify.js` - Validates Python installation
  - `start-all.js` - Uses detected Python command

### 3. **Environment Variable Validation**
- ❌ **Before**: Missing env vars caused silent failures
- ✅ **After**: Startup validation with clear error messages
- **Files Created**:
  - `services/api-gateway/app/utils/env_validation.py` - Validates Google OAuth config
  - `services/gmail-connector-service/app/utils/env_validation.py` - Validates required vars
- **Files Updated**:
  - `services/api-gateway/app/main.py` - Validates on startup
  - `services/gmail-connector-service/app/main.py` - Validates on startup

### 4. **Cross-Platform Scripts**
- ❌ **Before**: Separate `.sh` (Mac/Linux) and `.ps1` (Windows) scripts
- ✅ **After**: Node.js-based scripts that work everywhere
- **Files Created**:
  - `setup.js` - One-command setup for all platforms
  - `verify.js` - Environment verification
  - `start-all.js` - Cross-platform service launcher
  - `package.json` - Root-level package with npm scripts

### 5. **Documentation**
- ✅ **Created**: Comprehensive `README.md` with Windows + Mac instructions
- ✅ **Created**: `.env.example` template with all required variables
- ✅ **Created**: `.nvmrc` for Node.js version locking

## 🚀 Quick Start (All Platforms)

### Step 1: Setup
```bash
npm run setup
```

This will:
- Check Node.js and Python versions
- Create virtual environments for all services
- Install all dependencies
- Create `.env` file from template

### Step 2: Configure
Edit `.env` and add your Google OAuth credentials:
```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

### Step 3: Verify
```bash
npm run verify
```

### Step 4: Start
```bash
npm run dev
```

## 📋 Platform-Specific Notes

### Windows
- ✅ Works with both CMD and PowerShell
- ✅ Uses `python` command (not `python3`)
- ✅ Path separators handled automatically (`\` vs `/`)
- ✅ No manual path fixes needed

**Common Issues:**
1. **Python not in PATH**: Add Python to PATH during installation
2. **Permission errors**: Run PowerShell as Administrator if needed
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

### macOS
- ✅ Works out of the box
- ✅ Uses `python3` automatically
- ✅ Handles path separators correctly

**Common Issues:**
1. **Python 3 not found**: Install via Homebrew
   ```bash
   brew install python3
   ```

### Linux
- ✅ Works on Ubuntu, Debian, Fedora, etc.
- ✅ Uses `python3` automatically
- ✅ Handles path separators correctly

## 🔧 Technical Details

### Path Handling
All file paths now use:
- **Python**: `pathlib.Path` for cross-platform compatibility
- **Node.js**: `path.join()` and `path.resolve()` for absolute paths
- **Database URLs**: Absolute paths using `Path(__file__).parent.parent.parent`

### Environment Variables
Required variables are validated at startup:
- `GOOGLE_CLIENT_ID` - Required
- `GOOGLE_CLIENT_SECRET` - Required
- `GOOGLE_REDIRECT_URI` - Has default, validated for format
- Service URLs - Have defaults, validated for format

### Virtual Environments
- Created automatically by `setup.js`
- Located in `services/<service-name>/venv/`
- Activated automatically by start scripts
- Python executable path detected per platform

## 🐛 Troubleshooting

### Services Won't Start
1. Run `npm run verify` to check environment
2. Check logs in service terminal windows
3. Ensure `.env` file exists and has required variables

### OAuth Not Working
1. Verify credentials in `.env`
2. Check redirect URI matches Google Cloud Console exactly
3. Clear browser cache and try incognito window

### Database Issues
- SQLite databases are created automatically
- Paths are absolute and cross-platform
- Check file permissions if issues persist

## ✅ Cross-Platform Guarantees

- ✅ No hardcoded paths (`/Users/`, `C:\`, etc.)
- ✅ Path separators handled automatically
- ✅ Python version detection (`python` vs `python3`)
- ✅ Environment variable validation
- ✅ Cross-platform file permissions
- ✅ Works on Windows, macOS, and Linux

## 📝 Files Changed

### Created
- `setup.js` - Cross-platform setup script
- `verify.js` - Environment verification
- `start-all.js` - Cross-platform start script
- `.env.example` - Environment template
- `.nvmrc` - Node version lock
- `package.json` - Root package with scripts
- `CROSS_PLATFORM_SETUP.md` - This document

### Modified
- `services/application-service/app/api/resumes.py` - Path handling
- `services/application-service/app/config.py` - Database paths
- `services/gmail-connector-service/app/config.py` - Database paths
- `services/auth-service/app/config.py` - Database paths
- `services/api-gateway/app/main.py` - Environment validation
- `services/gmail-connector-service/app/main.py` - Environment validation
- `README.md` - Comprehensive cross-platform guide

## 🎯 Next Steps

1. Run `npm run setup` to initialize the project
2. Edit `.env` with your Google OAuth credentials
3. Run `npm run verify` to check everything is ready
4. Run `npm run dev` to start all services
5. Open http://localhost:5173 in your browser

## 🤝 Contributing

This project is designed for cross-platform collaboration:
- **Windows developers**: Use `npm run` commands or PowerShell scripts
- **Mac/Linux developers**: Use `npm run` commands or bash scripts
- **All platforms**: Use `npm run setup` and `npm run dev` for consistency
