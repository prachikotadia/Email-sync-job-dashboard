@echo off
REM JobPulse AI Setup Script for Windows

echo 🚀 Setting up JobPulse AI...

REM Check if Docker is installed
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker is not installed. Please install Docker Desktop for Windows first.
    exit /b 1
)

REM Check if Docker Compose is installed
where docker-compose >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  docker-compose not found, trying 'docker compose' (newer Docker Desktop)...
    docker compose version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Docker Compose is not installed. Please install Docker Desktop for Windows.
        exit /b 1
    )
)

REM Create .env file if it doesn't exist
if not exist .env (
    echo 📝 Creating .env file...
    if exist .env.example (
        copy .env.example .env
        echo ⚠️  Please update .env with your Google OAuth credentials!
    ) else (
        echo Creating basic .env file...
        (
            echo # JWT Configuration
            echo JWT_SECRET=
            echo JWT_ALGORITHM=HS256
            echo.
            echo # Google OAuth Configuration
            echo GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
            echo GOOGLE_CLIENT_SECRET=your-google-client-secret
            echo REDIRECT_URI=http://localhost:8001/auth/callback
            echo.
            echo # Service URLs (internal Docker network)
            echo AUTH_SERVICE_URL=http://auth-service:8001
            echo GMAIL_SERVICE_URL=http://gmail-connector:8002
            echo.
            echo # Frontend API URL
            echo VITE_API_URL=http://localhost:8000
        ) > .env
        echo ⚠️  Please update .env with your Google OAuth credentials!
        echo ⚠️  Note: Generate JWT_SECRET using: python -c "import secrets; print(secrets.token_hex(32))"
    )
) else (
    echo ✅ .env file already exists
)

REM Create volumes directory
if not exist volumes\gmail-sync-state (
    mkdir volumes\gmail-sync-state
)

echo.
echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Update .env with your Google OAuth credentials
echo 2. Run: docker-compose up --build
echo    (or: docker compose up --build if using newer Docker Desktop)
echo 3. Access the app at http://localhost:3000
echo.
