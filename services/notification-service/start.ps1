# Start script for notification-service with virtual environment

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

# Start the service
Write-Host "Starting notification-service on port 8005..." -ForegroundColor Cyan
& $pythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8005
