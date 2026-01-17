from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
from app.routers import auth, gmail
from app.middleware.auth_middleware import verify_token

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
GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector:8002")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(gmail.router, prefix="/api/gmail", tags=["gmail"])

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )
