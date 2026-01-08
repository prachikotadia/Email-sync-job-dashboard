from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.proxy import reverse_proxy

app = FastAPI(title="API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "api-gateway"}

# --- Routes ---

# Application Service Forwarding
@app.api_route("/applications/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def application_service_proxy(request: Request, path: str):
    return await reverse_proxy(request, settings.APPLICATION_SERVICE_URL, f"/applications/{path}")

# Ingest Endpoint (forwarding to app service as well for now)
@app.post("/ingest/{path:path}")
async def ingest_proxy(request: Request, path: str):
    return await reverse_proxy(request, settings.APPLICATION_SERVICE_URL, f"/ingest/{path}")

# Auth Service Stub
@app.api_route("/auth/{path:path}", methods=["GET", "POST"])
async def auth_service_proxy(request: Request, path: str):
    return await reverse_proxy(request, settings.AUTH_SERVICE_URL, f"/auth/{path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
