"""
Export Router - Proxies export requests to gmail-connector service
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import os
from app.middleware.auth_middleware import verify_token

router = APIRouter()

GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")

class ExportRequest(BaseModel):
    format: str  # csv, xlsx, json, pdf
    category: str  # ALL, APPLIED, REJECTED, INTERVIEW, OFFER, GHOSTED
    dateRange: Dict[str, Any]  # { "from": "YYYY-MM-DD" | null, "to": "YYYY-MM-DD" | null }
    fields: List[str]  # List of field names to include

@router.post("/export")
async def export_applications(
    request: ExportRequest,
    token_data: dict = Depends(verify_token)
):
    """
    Export applications in various formats
    Proxies to gmail-connector service
    """
    user_id = token_data.get("sub")  # Email from JWT
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/export",
                json=request.dict(),
                params={"user_id": user_id}
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            if response.status_code == 400:
                error_detail = response.json().get("detail", "Invalid request")
                raise HTTPException(status_code=400, detail=error_detail)
            
            response.raise_for_status()
            
            # Return file response
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "application/octet-stream"),
                headers={
                    "Content-Disposition": response.headers.get("content-disposition", ""),
                    "Content-Length": response.headers.get("content-length", ""),
                },
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_detail = e.response.json().get("detail", "Invalid request")
            raise HTTPException(status_code=400, detail=error_detail)
        raise HTTPException(status_code=e.response.status_code, detail=f"Export failed: {str(e)}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Export request timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Gmail service unavailable: {str(e)}")
