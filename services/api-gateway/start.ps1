# Start script for api-gateway with virtual environment

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

# Use venv Python explicitly
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

# Check if .env exists
if (-not (Test-Path (Join-Path $scriptPath ".env"))) {
    Write-Host "⚠️  .env file not found. Creating from defaults..." -ForegroundColor Yellow
    # .env should have been created by setup-env.ps1
}

# Start the service
Write-Host "Starting api-gateway on port 8000..." -ForegroundColor Cyan
Write-Host "Make sure auth-service (8003) and application-service (8002) are running!" -ForegroundColor Yellow
& $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
