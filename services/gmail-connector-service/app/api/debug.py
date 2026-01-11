"""
Debug endpoints for development (DEV ONLY).
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header
from app.api.gmail_auth import get_user_from_jwt
from app.api.gmail_sync import get_gmail_credentials_async
from app.security.token_verification import verify_token_scopes
from app.config import get_settings
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/debug/gmail/scopes")
async def debug_gmail_scopes(
    user: dict = Depends(get_user_from_jwt),
    authorization: str = Header(None)
):
    """
    Debug endpoint to check Gmail token scopes (DEV ONLY).
    
    Returns:
    - stored_scopes: Scopes from database
    - tokeninfo_scopes: Scopes from Google tokeninfo (actual token scopes)
    - has_readonly: Whether gmail.readonly is present
    - has_metadata: Whether gmail.metadata is present
    
    Protected by ENV=dev check.
    """
    # DEV ONLY - check environment
    if settings.ENV != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug endpoints are only available in development mode"
        )
    
    user_id = user.get("id")
    access_token = authorization.replace("Bearer ", "") if authorization else None
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    try:
        # Get stored scopes from database
        stored_scopes = []
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.AUTH_SERVICE_URL}/api/gmail/tokens",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5.0
                )
                if response.status_code == 200:
                    tokens_dict = response.json().get("tokens", {})
                    stored_scopes = tokens_dict.get("scopes", [])
        except Exception as e:
            logger.warning(f"Could not get stored scopes: {e}")
        
        # Get credentials and verify with tokeninfo
        tokeninfo_result = None
        tokeninfo_scopes = []
        has_readonly = False
        has_metadata = False
        
        try:
            credentials = await get_gmail_credentials_async(user_id, access_token)
            tokeninfo_result = await verify_token_scopes(credentials.token)
            tokeninfo_scopes = tokeninfo_result.get("scopes", [])
            has_readonly = tokeninfo_result.get("has_readonly", False)
            has_metadata = tokeninfo_result.get("has_metadata", False)
        except Exception as e:
            logger.warning(f"Could not verify token scopes: {e}")
        
        return {
            "user_id": user_id,
            "stored_scopes": stored_scopes,
            "tokeninfo_scopes": tokeninfo_scopes,
            "has_readonly": has_readonly,
            "has_metadata": has_metadata,
            "readonly_required": True,
            "metadata_allowed": False
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug endpoint error: {str(e)}"
        )
