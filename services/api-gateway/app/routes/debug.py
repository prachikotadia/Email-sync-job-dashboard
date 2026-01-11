"""
Debug endpoints (development only).
"""
from fastapi import APIRouter, HTTPException, Depends
from app.config import get_settings, get_google_redirect_uri
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def check_dev_mode():
    """Dependency to ensure endpoint is only available in dev mode."""
    if settings.ENV != "dev":
        raise HTTPException(status_code=404, detail="Debug endpoint not available in production")
    return True


@router.get("/debug/oauth")
async def debug_oauth(_: bool = Depends(check_dev_mode)):
    """
    Debug endpoint to show OAuth configuration (DEV ONLY).
    
    Returns the exact redirect URI that should be registered in Google Cloud Console.
    """
    try:
        redirect_uri = get_google_redirect_uri()
        
        # Get gateway base URL from redirect URI
        # Extract protocol and host from redirect URI
        if redirect_uri.startswith("http://localhost"):
            gateway_base_url = "http://localhost:8000"
        elif redirect_uri.startswith("https://"):
            # Extract domain from redirect URI
            parts = redirect_uri.replace("https://", "").split("/")
            gateway_base_url = f"https://{parts[0]}"
        else:
            gateway_base_url = "unknown"
        
        # Determine if redirect URI points to gateway or gmail-connector-service
        is_gateway = "8000" in redirect_uri or "gateway" in redirect_uri.lower()
        is_connector = "8001" in redirect_uri or "gmail-connector" in redirect_uri.lower()
        
        return {
            "redirect_uri": redirect_uri,
            "gateway_base_url": gateway_base_url,
            "redirect_target": "gateway" if is_gateway else ("gmail-connector-service" if is_connector else "unknown"),
            "note": "Register this exact redirect_uri in Google Cloud Console 'Authorized redirect URIs'. This URI must match EXACTLY what's in your .env file.",
            "google_cloud_console_instructions": {
                "step_1": "Go to Google Cloud Console → APIs & Services → Credentials",
                "step_2": "Click on your OAuth 2.0 Client ID",
                "step_3": f"Under 'Authorized redirect URIs', add exactly: {redirect_uri}",
                "step_4": "Click Save",
                "important": "The redirect URI in Google Cloud Console must match EXACTLY the GOOGLE_REDIRECT_URI in your .env file (character-for-character, including port number)"
            }
        }
    except Exception as e:
        logger.error(f"Error in debug/oauth endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving OAuth config: {str(e)}")
