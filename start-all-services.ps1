# Master script to start all services and frontend
# Run this from the project root directory

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting All Services and Frontend" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to start a service
function Start-MyService {
    param(
        [string]$ServiceName,
        [string]$ServicePath,
        [int]$Port
    )
    
    Write-Host "Starting $ServiceName on port $Port..." -ForegroundColor Yellow
    
    $fullPath = Join-Path $projectRoot $ServicePath
    $startScript = Join-Path $fullPath "start.ps1"
    
    if (Test-Path $startScript) {
        Start-Process powershell -ArgumentList "-NoExit", "-File", $startScript
        Write-Host "  ✓ $ServiceName started" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Start script not found: $startScript" -ForegroundColor Red
    }
    
    Start-Sleep -Milliseconds 500
}

# Start all backend services
Start-MyService -ServiceName "auth-service" -ServicePath "services\auth-service" -Port 8003
Start-MyService -ServiceName "gmail-connector-service" -ServicePath "services\gmail-connector-service" -Port 8001
Start-MyService -ServiceName "application-service" -ServicePath "services\application-service" -Port 8002
Start-MyService -ServiceName "email-intelligence-service" -ServicePath "services\email-intelligence-service" -Port 8004
Start-MyService -ServiceName "notification-service" -ServicePath "services\notification-service" -Port 8005
Start-MyService -ServiceName "api-gateway" -ServicePath "services\api-gateway" -Port 8000

# Start frontend
Write-Host ""
Write-Host "Starting frontend on port 5173..." -ForegroundColor Yellow
$frontendPath = Join-Path $projectRoot "frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev"
Write-Host "  ✓ Frontend started" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All services starting..." -ForegroundColor Cyan
Write-Host "Check the PowerShell windows for status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services should be available at:" -ForegroundColor Green
Write-Host "  - Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  - API Gateway: http://localhost:8000" -ForegroundColor White
Write-Host "  - Auth Service: http://localhost:8003" -ForegroundColor White
Write-Host "  - Gmail Connector: http://localhost:8001" -ForegroundColor White
Write-Host "  - Application Service: http://localhost:8002" -ForegroundColor White
Write-Host "  - Email Intelligence: http://localhost:8004" -ForegroundColor White
Write-Host "  - Notification Service: http://localhost:8005" -ForegroundColor White
