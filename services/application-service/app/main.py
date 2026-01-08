from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import health, applications, resumes, export, ingest
from app.config import settings
# from app.db.supabase import create_tables # Uncomment to auto-migrate on start

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(applications.router, prefix="/applications", tags=["Applications"])
app.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
app.include_router(export.router, prefix="/export", tags=["Export"])
# Internal Ingest Endpoint (Phase 6 but useful stub)
app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
