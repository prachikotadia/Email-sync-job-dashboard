# Where to Find Log Files

## Current Logging Setup

By default, all services log to the **console/terminal** where they're running. There's no file logging configured, so logs appear in real-time in the terminal window.

## Log Locations

### 1. **Console/Terminal Output** (Primary Location)

When you run a service, logs appear directly in the terminal:

**API Gateway:**
```powershell
cd services/api-gateway
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
→ Logs appear in this terminal window

**Gmail Connector Service:**
```powershell
cd services/gmail-connector-service
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```
→ Logs appear in this terminal window

### 2. **Log Files** (If Any)

**Found log file:**
- `services/api-gateway/uvicorn_gateway.log` - Contains some uvicorn logs

**Note:** Most services don't create log files by default. Logs go to stdout/stderr (console).

## How to View Logs

### Option 1: View in Terminal (Real-time)

1. **Keep the terminal window open** where the service is running
2. **Watch the logs** as they appear in real-time
3. **Look for debug sections** marked with:
   - `=== TOKEN EXCHANGE DEBUG INFO ===`
   - `=== AUTHORIZATION URL GENERATION DEBUG ===`
   - `=== CALLBACK PROCESSING DEBUG ===`

### Option 2: Redirect Logs to File

You can redirect logs to a file when starting the service:

**Windows PowerShell:**
```powershell
# API Gateway
cd services/api-gateway
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 *> gateway.log

# Gmail Connector Service
cd services/gmail-connector-service
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 *> gmail_connector.log
```

**Or use Tee to see in console AND save to file:**
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 | Tee-Object -FilePath gmail_connector.log
```

### Option 3: Check Existing Log File

```powershell
# View API Gateway log
Get-Content services/api-gateway/uvicorn_gateway.log -Tail 50

# Or open in notepad
notepad services/api-gateway/uvicorn_gateway.log
```

## What to Look For in Logs

When debugging OAuth redirect URI issues, look for these sections:

### Authorization URL Generation:
```
=== AUTHORIZATION URL GENERATION DEBUG ===
Redirect URI in flow: 'http://localhost:8000/auth/gmail/callback'
Redirect URI length: 47
Redirect URI bytes: b'http://localhost:8000/auth/gmail/callback'
Client ID: 123456789-abc.apps...
State token: FlisWW0-CFec2UXN72AEnBnnP2um4HU2...
==========================================
```

### Token Exchange:
```
=== TOKEN EXCHANGE DEBUG INFO ===
Redirect URI being used: 'http://localhost:8000/auth/gmail/callback'
Redirect URI length: 47
Flow redirect_uri: 'http://localhost:8000/auth/gmail/callback'
Redirect URIs match: True
=================================
```

### Errors:
```
=== TOKEN EXCHANGE ERROR ===
Error Type: RedirectURIMismatchError
Error Message: redirect_uri_mismatch
Redirect URI Used: 'http://localhost:8000/auth/gmail/callback'
Flow Redirect URI: 'http://localhost:8000/auth/gmail/callback'
Diagnosis: REDIRECT URI MISMATCH DETECTED!
...
============================
```

## Quick Commands to View Recent Logs

### If running in terminal:
- **Scroll up** in the terminal to see previous logs
- Use **Ctrl+F** to search for specific terms like "redirect_uri" or "ERROR"

### If you want to save logs to a file:
```powershell
# Start service and save logs
cd services/gmail-connector-service
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 2>&1 | Tee-Object -FilePath gmail_connector.log
```

Then view the log file:
```powershell
Get-Content gmail_connector.log -Tail 100
```

## Recommended: Keep Terminal Open

The easiest way to see logs is to:
1. **Keep the terminal window open** where you started the service
2. **Watch the logs in real-time** as requests come in
3. **Look for the debug sections** when OAuth flow runs

## Next Steps

If you want to configure file logging, we can add logging configuration to write logs to files automatically. Would you like me to set that up?
