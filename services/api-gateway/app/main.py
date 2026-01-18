from fastapi import FastAPI, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
import os
import time
from datetime import datetime, timezone
from app.routers import auth, gmail
from app.middleware.auth_middleware import verify_token

_health_start = time.time()

app = FastAPI(title="JobPulse API Gateway")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")
CLASSIFIER_SERVICE_URL = os.getenv("CLASSIFIER_SERVICE_URL", "http://host.docker.internal:8003")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(gmail.router, prefix="/api/gmail", tags=["gmail"])



async def _probe(url: str, path: str = "/health") -> dict:
    try:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{url.rstrip('/')}{path}")
        ms = round((time.perf_counter() - t0) * 1000)
        return {"status": "ok" if r.status_code == 200 else "error", "status_code": r.status_code, "latency_ms": ms}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint (without /api prefix) for consistency with other services."""
    auth_d = await _probe(AUTH_SERVICE_URL)
    gmail_d = await _probe(GMAIL_SERVICE_URL)
    classifier_d = await _probe(CLASSIFIER_SERVICE_URL)
    deps = {"auth_service": auth_d, "gmail_service": gmail_d, "classifier_service": classifier_d}
    all_ok = all(d.get("status") == "ok" for d in deps.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "service": "api-gateway",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "uptime_seconds": round(time.time() - _health_start, 2),
        "dependencies": deps,
    }


@app.get("/api/health")
async def api_health():
    """Health check endpoint (with /api prefix) for backward compatibility."""
    return await health()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )
