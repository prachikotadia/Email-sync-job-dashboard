# How to Start Gmail Connector Service

You need to activate the virtual environment first!

## Step-by-Step Instructions

### Step 1: Navigate to the service directory
```bash
cd services/gmail-connector-service
```

### Step 2: Activate the virtual environment

**For PowerShell (Windows):**
```powershell
.\venv\Scripts\Activate.ps1
```

If you get an execution policy error, run this first:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Alternative for PowerShell (if Activate.ps1 doesn't work):**
```powershell
.\venv\Scripts\activate.bat
```

**For Command Prompt (cmd):**
```cmd
venv\Scripts\activate.bat
```

**For Linux/Mac:**
```bash
source venv/bin/activate
```

### Step 3: Verify activation

After activating, you should see `(venv)` at the beginning of your prompt:
```
(venv) PS C:\Users\...\services\gmail-connector-service>
```

### Step 4: Run the service

Once the virtual environment is activated, run:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

---

## Quick Command (PowerShell)

Run these commands in sequence:

```powershell
cd services/gmail-connector-service
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

---

## If You Get Execution Policy Error

If PowerShell says "cannot be loaded because running scripts is disabled", run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating again:
```powershell
.\venv\Scripts\Activate.ps1
```

---

## Verify It's Working

After starting, you should see:
```
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

Then test it:
```bash
# In another terminal
curl http://localhost:8001/health
```

You should get: `{"status":"healthy","service":"gmail-connector-service"}`
