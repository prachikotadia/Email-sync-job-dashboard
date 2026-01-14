# Script to switch back to Supabase
# Prompts for the Supabase connection string

Write-Host "Switching auth-service to Supabase..." -ForegroundColor Cyan

$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found at $envFile" -ForegroundColor Red
    exit 1
}

# Check for backup files
$backupFiles = Get-ChildItem "$envFile.backup.*" | Sort-Object LastWriteTime -Descending
if ($backupFiles.Count -eq 0) {
    Write-Host "No backup files found. Please enter your Supabase connection string:" -ForegroundColor Yellow
    $supabaseUrl = Read-Host "Supabase URL (postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres)"
} else {
    Write-Host "Found backup files. Restore from backup? (Y/n)" -ForegroundColor Yellow
    $restore = Read-Host
    if ($restore -eq "" -or $restore -eq "Y" -or $restore -eq "y") {
        $latestBackup = $backupFiles[0].FullName
        Write-Host "Restoring from: $latestBackup" -ForegroundColor Green
        Copy-Item $latestBackup $envFile -Force
        Write-Host "Restored successfully!" -ForegroundColor Green
        Write-Host "Restart the auth-service for changes to take effect." -ForegroundColor Yellow
        exit 0
    } else {
        Write-Host "Please enter your Supabase connection string:" -ForegroundColor Yellow
        $supabaseUrl = Read-Host "Supabase URL"
    }
}

if ($supabaseUrl) {
    # Backup current .env
    $backupFile = "$envFile.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $envFile $backupFile
    Write-Host "Backed up current .env to: $backupFile" -ForegroundColor Yellow

    # Read current .env
    $content = Get-Content $envFile -Raw

    # Replace AUTH_DATABASE_URL
    if ($content -match "AUTH_DATABASE_URL=.*") {
        $content = $content -replace "AUTH_DATABASE_URL=.*", "AUTH_DATABASE_URL=$supabaseUrl"
    } else {
        $content += "`nAUTH_DATABASE_URL=$supabaseUrl`n"
    }

    # Write back
    Set-Content -Path $envFile -Value $content -NoNewline

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Switched to Supabase successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Restart the auth-service for changes to take effect." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To test connection, run:" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\python.exe test_connection.py" -ForegroundColor White
}
