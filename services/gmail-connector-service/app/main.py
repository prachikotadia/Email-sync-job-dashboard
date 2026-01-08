from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import random
from datetime import datetime

app = FastAPI(title="Email AI Service")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EmailPayload(BaseModel):
    email_id: str
    subject: str
    sender: str
    received_at: str
    company_name: str
    application_status: str
    summary: str
    confidence_score: float

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "email-ai-service"}

@app.get("/auth/url")
def get_auth_url():
    # Placeholder for real OAuth URL generation
    return {"url": "https://accounts.google.com/o/oauth2/auth?mock=true"}

@app.post("/gmail/sync")
def sync_gmail():
    # Mock data generation
    mock_emails = [
        {
            "email_id": f"msg_{random.randint(1000, 9999)}",
            "subject": "Interview Invitation - Frontend Engineer",
            "sender": "recruiting@google.com",
            "received_at": datetime.now().isoformat(),
            "company_name": "Google",
            "application_status": "Interview",
            "summary": "Inviting you to a technical interview next Tuesday.",
            "confidence_score": 0.95
        },
        {
            "email_id": f"msg_{random.randint(1000, 9999)}",
            "subject": "Application Received",
            "sender": "jobs@netflix.com",
            "received_at": datetime.now().isoformat(),
            "company_name": "Netflix",
            "application_status": "Applied",
            "summary": "We have received your application for Senior Engineer.",
            "confidence_score": 0.88
        }
    ]
    return {"status": "synced", "count": len(mock_emails), "emails": mock_emails}
