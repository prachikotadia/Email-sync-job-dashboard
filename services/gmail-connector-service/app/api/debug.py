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


@router.get("/debug/sample-classification")
async def debug_sample_classification(
    user: dict = Depends(get_user_from_jwt),
    authorization: str = Header(None)
):
    """
    DEBUG ENDPOINT: Returns 10 sample email classifications for debugging.
    Shows what the classifier would do with sample emails.
    """
    # Sample emails for testing
    sample_emails = [
        {
            "id": "sample_1",
            "subject": "Thank you for applying to Software Engineer position",
            "from": "careers@company.com",
            "snippet": "We have received your application for the Software Engineer role",
            "body_text": "Thank you for applying to our Software Engineer position. We have received your application and will review it shortly."
        },
        {
            "id": "sample_2",
            "subject": "Interview invitation - Product Manager",
            "from": "recruiting@techcorp.com",
            "snippet": "We would like to invite you to an interview",
            "body_text": "We would like to invite you to an interview for the Product Manager position. Please let us know your availability."
        },
        {
            "id": "sample_3",
            "subject": "Application update",
            "from": "noreply@greenhouse.io",
            "snippet": "Your application status has been updated",
            "body_text": "Your application status has been updated. Please check your dashboard for details."
        },
        {
            "id": "sample_4",
            "subject": "Unfortunately, we will not be moving forward",
            "from": "talent@startup.com",
            "snippet": "After careful consideration, we have decided not to move forward",
            "body_text": "Unfortunately, after careful consideration, we have decided not to move forward with your application."
        },
        {
            "id": "sample_5",
            "subject": "Job offer - Senior Developer",
            "from": "hr@bigtech.com",
            "snippet": "We are pleased to offer you the position",
            "body_text": "We are pleased to offer you the position of Senior Developer. Congratulations!"
        },
        {
            "id": "sample_6",
            "subject": "Coding challenge invitation",
            "from": "assessments@company.com",
            "snippet": "Please complete the coding challenge",
            "body_text": "Please complete the coding challenge for the Software Engineer position."
        },
        {
            "id": "sample_7",
            "subject": "Newsletter - Weekly Jobs",
            "from": "newsletter@jobsite.com",
            "snippet": "Check out these new job opportunities",
            "body_text": "Check out these new job opportunities that match your profile."
        },
        {
            "id": "sample_8",
            "subject": "Verification code",
            "from": "noreply@service.com",
            "snippet": "Your verification code is 123456",
            "body_text": "Your verification code is 123456. Please enter this code to verify your account."
        },
        {
            "id": "sample_9",
            "subject": "Next steps in your application",
            "from": "talent@company.com",
            "snippet": "Here are the next steps in your application process",
            "body_text": "Here are the next steps in your application process. We will be in touch soon."
        },
        {
            "id": "sample_10",
            "subject": "Re: Your application",
            "from": "recruiter@company.com",
            "snippet": "Following up on your application",
            "body_text": "Following up on your application. We are still reviewing candidates."
        },
    ]
    
    results = []
    for email in sample_emails:
        email_data = {
            "id": email["id"],
            "subject": email["subject"],
            "from": email["from"],
            "to": "",
            "snippet": email["snippet"],
            "body_text": email["body_text"]
        }
        
        try:
            classification = classify_job_email(email_data)
            results.append({
                "email_id": email["id"],
                "subject": email["subject"],
                "from": email["from"],
                "classification": {
                    "status": classification.get("status"),
                    "confidence": classification.get("confidence"),
                    "reason": classification.get("reason"),
                    "is_job_email": classification.get("is_job_email"),
                    "should_store": classification.get("should_store"),
                    "company": classification.get("company"),
                }
            })
        except Exception as e:
            results.append({
                "email_id": email["id"],
                "subject": email["subject"],
                "from": email["from"],
                "error": str(e)
            })
    
    return {
        "total_samples": len(sample_emails),
        "classifications": results
    }


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
