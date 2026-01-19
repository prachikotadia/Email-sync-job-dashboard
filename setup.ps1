# JobPulse AI Setup Script for Windows PowerShell

Write-Host "🚀 Setting up JobPulse AI..." -ForegroundColor Cyan

# Check if Docker is installed
try {
    $null = Get-Command docker -ErrorAction Stop
    Write-Host "✅ Docker found" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop for Windows first." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is installed
$dockerComposeCmd = $null
try {
    $null = Get-Command docker-compose -ErrorAction Stop
    $dockerComposeCmd = "docker-compose"
    Write-Host "✅ docker-compose found" -ForegroundColor Green
} catch {
    try {
        $null = docker compose version 2>$null
        $dockerComposeCmd = "docker compose"
        Write-Host "✅ docker compose found (newer Docker Desktop)" -ForegroundColor Green
    } catch {
        Write-Host "❌ Docker Compose is not installed. Please install Docker Desktop for Windows." -ForegroundColor Red
        exit 1
    }
}

# Create .env file if it doesn't exist
if (-not (Test-Path .env)) {
    Write-Host "📝 Creating .env file..." -ForegroundColor Yellow
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Host "⚠️  Please update .env with your Google OAuth credentials!" -ForegroundColor Yellow
    } else {
        Write-Host "Creating basic .env file..." -ForegroundColor Yellow
        
        # Generate JWT_SECRET
        $jwtSecret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
        $jwtSecretHex = -join ((0..9) + ('a'..'f') | Get-Random -Count 64)
        
        $envContent = @"
# JWT Configuration
JWT_SECRET=$jwtSecretHex
JWT_ALGORITHM=HS256

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
REDIRECT_URI=http://localhost:8001/auth/callback

# Service URLs (internal Docker network)
AUTH_SERVICE_URL=http://auth-service:8001
GMAIL_SERVICE_URL=http://gmail-connector:8002

# Frontend API URL
VITE_API_URL=http://localhost:8000
"@
        $envContent | Out-File -FilePath .env -Encoding utf8
        Write-Host "⚠️  Please update .env with your Google OAuth credentials!" -ForegroundColor Yellow
    }
} else {
    Write-Host "✅ .env file already exists" -ForegroundColor Green
}

# Create volumes directory
if (-not (Test-Path "volumes\gmail-sync-state")) {
    New-Item -ItemType Directory -Path "volumes\gmail-sync-state" -Force | Out-Null
}

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update .env with your Google OAuth credentials"
Write-Host "2. Run: $dockerComposeCmd up --build"
Write-Host "3. Access the app at http://localhost:3000"
Write-Host ""
