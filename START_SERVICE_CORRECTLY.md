# How to Start Gmail Connector Service (Correct Steps)

You're getting "ModuleNotFoundError: No module named 'app'" because you're in the wrong directory.

## Correct Steps

### Step 1: Navigate to the service directory
```powershell
cd services/gmail-connector-service
```

### Step 2: Activate the virtual environment
```powershell
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` at the start of your prompt:
```
(venv) PS C:\Users\...\services\gmail-connector-service>
```

### Step 3: Run the service
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

---

## All-in-One Command (Copy and Paste)

```powershell
cd services/gmail-connector-service; .\venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

This does all three steps in one command.

---

## Why This Happens

- The `app` module is located in `services/gmail-connector-service/app/`
- You must be in the `services/gmail-connector-service` directory for Python to find the `app` module
- The virtual environment must be activated to use the installed packages

---

## Verify You're in the Right Directory

Before running uvicorn, check:
```powershell
Get-Location
```

Should show:
```
Path
----
C:\Users\...\services\gmail-connector-service
```

And you should see the `app` folder:
```powershell
ls app
```

Should show:
```
app/
  __pycache__/
  api/
  config.py
  main.py
  schemas/
  security/
  db/
```

---

## After Starting Successfully

You should see:
```
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

Then test:
- Open: http://localhost:8001/health
- Should return: `{"status":"healthy","service":"gmail-connector-service"}`
