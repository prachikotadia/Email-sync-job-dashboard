from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, ingest, applications, export, resumes
from app.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="The source of truth for job applications."
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router, tags=["Health"])
app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
app.include_router(applications.router, prefix="/applications", tags=["Applications"])
app.include_router(export.router, prefix="/export", tags=["Export"])
app.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
