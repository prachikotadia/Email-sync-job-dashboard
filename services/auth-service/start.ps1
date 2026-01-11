# Start script for auth-service with virtual environment

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $scriptPath "venv"

# Check if virtual environment exists
if (-not (Test-Path $venvPath)) {
    Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    
    python -m venv $venvPath
    & (Join-Path $venvPath "Scripts\Activate.ps1")
    python -m pip install --upgrade pip
    python -m pip install -r (Join-Path $scriptPath "requirements.txt")
    deactivate
    
    Write-Host "✅ Virtual environment created and dependencies installed" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& (Join-Path $venvPath "Scripts\Activate.ps1")

# Check if .env exists
if (-not (Test-Path (Join-Path $scriptPath ".env"))) {
    Write-Host "⚠️  .env file not found. Creating from defaults..." -ForegroundColor Yellow
    # .env should have been created by setup-env.ps1
}

# Start the service
Write-Host "Starting auth-service on port 8003..." -ForegroundColor Cyan
python -m uvicorn app.main:app --reload --port 8003
