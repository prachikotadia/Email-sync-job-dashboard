from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import os
import pandas as pd
from datetime import datetime

app = FastAPI(title="Application Service")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "application-service"}

@app.get("/applications")
def get_applications():
    # Mock data
    return [
        {
            "id": 1,
            "company": "Google",
            "position": "Frontend Engineer",
            "status": "Interview",
            "date": "2023-10-15"
        },
        {
            "id": 2,
            "company": "Netflix",
            "position": "Senior Engineer",
            "status": "Applied",
            "date": "2023-10-18"
        }
    ]

@app.get("/export/excel")
def export_excel():
    # Create dummy dataframe
    df = pd.DataFrame([
        {"Company": "Google", "Status": "Interview", "Date": "2023-10-15"},
        {"Company": "Netflix", "Status": "Applied", "Date": "2023-10-18"}
    ])
    
    filename = "applications_export.xlsx"
    df.to_excel(filename, index=False)
    
    return FileResponse(path=filename, filename=filename, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
