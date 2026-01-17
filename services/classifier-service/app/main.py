# Step 3: Base only. No classification logic yet.
# Step 6 will add: stage1_high_recall, stage2_high_precision, ghosted, /classify.
import time
from datetime import datetime, timezone
from fastapi import FastAPI

_health_start = time.time()

app = FastAPI(title="Classifier Service")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "classifier-service",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "uptime_seconds": round(time.time() - _health_start, 2),
    }


@app.get("/")
def root():
    return {"service": "classifier-service", "docs": "/docs"}
