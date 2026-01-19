"""
Profile Router - Proxies profile requests to gmail-connector-service
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import os
from app.middleware.auth_middleware import verify_token

router = APIRouter()

GMAIL_SERVICE_URL = os.getenv("GMAIL_SERVICE_URL", "http://gmail-connector-service:8002")


class ProfileLinkCreate(BaseModel):
    type: str
    label: Optional[str] = None
    url: str


class ProfileLinkUpdate(BaseModel):
    type: Optional[str] = None
    label: Optional[str] = None
    url: Optional[str] = None


@router.get("/profile/links")
async def get_profile_links(token_data: dict = Depends(verify_token)):
    """
    Get all profile links for the current user.
    """
    user_id = token_data.get("sub")  # Email from JWT
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GMAIL_SERVICE_URL}/profile/links",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Profile service unavailable: {str(e)}")


@router.post("/profile/links")
async def create_profile_link(
    link_data: ProfileLinkCreate,
    token_data: dict = Depends(verify_token)
):
    """
    Create a new profile link.
    """
    user_id = token_data.get("sub")  # Email from JWT
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GMAIL_SERVICE_URL}/profile/links",
                params={"user_id": user_id},
                json=link_data.dict()
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        if e.response:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        raise HTTPException(status_code=503, detail=f"Profile service unavailable: {str(e)}")


@router.put("/profile/links/{link_id}")
async def update_profile_link(
    link_id: str,
    link_data: ProfileLinkUpdate,
    token_data: dict = Depends(verify_token)
):
    """
    Update an existing profile link.
    """
    user_id = token_data.get("sub")  # Email from JWT
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{GMAIL_SERVICE_URL}/profile/links/{link_id}",
                params={"user_id": user_id},
                json=link_data.dict(exclude_none=True)
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        if e.response:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        raise HTTPException(status_code=503, detail=f"Profile service unavailable: {str(e)}")


@router.delete("/profile/links/{link_id}")
async def delete_profile_link(
    link_id: str,
    token_data: dict = Depends(verify_token)
):
    """
    Delete a profile link.
    """
    user_id = token_data.get("sub")  # Email from JWT
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{GMAIL_SERVICE_URL}/profile/links/{link_id}",
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        if e.response:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        raise HTTPException(status_code=503, detail=f"Profile service unavailable: {str(e)}")
