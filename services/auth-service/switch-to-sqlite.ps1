# Quick script to switch to SQLite for local development
# This is useful when Supabase is unavailable

Write-Host "Switching auth-service to SQLite..." -ForegroundColor Cyan

$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found at $envFile" -ForegroundColor Red
    exit 1
}

# Backup original .env
$backupFile = "$envFile.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $envFile $backupFile
Write-Host "Backed up .env to: $backupFile" -ForegroundColor Yellow

# Read current .env
$content = Get-Content $envFile -Raw

# Replace AUTH_DATABASE_URL with SQLite
if ($content -match "AUTH_DATABASE_URL=.*") {
    $content = $content -replace "AUTH_DATABASE_URL=.*", "AUTH_DATABASE_URL=sqlite:///./auth.db"
    Write-Host "Updated AUTH_DATABASE_URL to SQLite" -ForegroundColor Green
} else {
    # Add it if it doesn't exist
    $content += "`nAUTH_DATABASE_URL=sqlite:///./auth.db`n"
    Write-Host "Added AUTH_DATABASE_URL with SQLite" -ForegroundColor Green
}

# Write back
Set-Content -Path $envFile -Value $content -NoNewline

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Switched to SQLite successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To restore Supabase, run:" -ForegroundColor Yellow
Write-Host "  Copy-Item '$backupFile' '$envFile' -Force" -ForegroundColor White
Write-Host ""
Write-Host "Restart the auth-service for changes to take effect." -ForegroundColor Yellow
