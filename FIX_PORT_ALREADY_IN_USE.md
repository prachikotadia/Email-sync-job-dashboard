# Fix: Port 8001 Already in Use

Error: `[winerror 10048] only one usage of each socket address (protocol/network address/port) is normally permitted`

This means another instance of the gmail-connector-service is already running on port 8001.

## Quick Fix

### Option 1: Kill the Process Using Port 8001 (Recommended)

1. **Find the process ID (PID):**
   ```powershell
   netstat -ano | findstr :8001
   ```
   This will show something like:
   ```
   TCP    0.0.0.0:8001           0.0.0.0:0              LISTENING       12345
   ```
   Note the last number (12345) - that's the Process ID (PID)

2. **Kill the process:**
   ```powershell
   taskkill /PID <PID> /F
   ```
   Replace `<PID>` with the number you found (e.g., `taskkill /PID 12345 /F`)

3. **Start the service again:**
   ```powershell
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```

### Option 2: Find and Kill Python/Uvicorn Processes

1. **Find all Python processes:**
   ```powershell
   Get-Process python | Select-Object Id, ProcessName, Path
   ```

2. **Kill specific process:**
   ```powershell
   Stop-Process -Id <PID> -Force
   ```

### Option 3: Use a Different Port (Temporary)

If you can't kill the process, use a different port temporarily:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

**Note:** If you do this, you also need to update:
- API Gateway config to point to port 8002
- Or just kill the old process and use port 8001

---

## One-Line Solution (PowerShell)

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8001).OwningProcess | Stop-Process -Force
```

This automatically finds and kills the process using port 8001.

---

## After Killing the Process

1. **Verify port is free:**
   ```powershell
   netstat -ano | findstr :8001
   ```
   Should return nothing (port is free)

2. **Start the service:**
   ```powershell
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```

---

## Prevent This in the Future

- Always stop the service properly (Ctrl+C) before starting it again
- Check if port is in use before starting: `netstat -ano | findstr :8001`
- Use a process manager if you need multiple instances
