"""
Gmail email sync endpoint - fetches emails and processes them.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header
from fastapi.responses import StreamingResponse
from app.schemas.gmail import GmailConnectionStatus
from app.config import get_settings
from app.security.token_verification import verify_token_scopes, require_readonly_scope
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import httpx
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


async def get_user_from_jwt(authorization: str = Header(None)) -> dict:
    """Extract user info from JWT token (validated by API Gateway)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    token = authorization.replace("Bearer ", "")
    
    # Verify token with auth-service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error verifying token with auth-service: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable"
        )


async def get_gmail_credentials_async(user_id: str, access_token: str) -> Credentials:
    """Get Gmail OAuth credentials for the user (async version)."""
    try:
        # Get tokens from auth-service
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/gmail/tokens",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to get Gmail tokens"
                )
            tokens_dict = response.json()["tokens"]
        
        # Get scopes and filter out metadata scope - ONLY use readonly for API calls
        original_scopes = tokens_dict.get("scopes", [])
        
        # CRITICAL: Completely remove metadata scope - NEVER use it
        # The logic before was wrong: 'gmail.metadata' not in scope OR 'gmail.readonly' in scope
        # This would keep metadata if readonly was present!
        # Now we explicitly filter out metadata ALWAYS
        filtered_scopes = [
            scope for scope in original_scopes 
            if 'gmail.metadata' not in scope  # Remove metadata scope completely
        ]
        
        # Verify we have readonly scope after filtering
        has_readonly = 'https://www.googleapis.com/auth/gmail.readonly' in filtered_scopes
        if not has_readonly:
            logger.error(f"ERROR: No gmail.readonly scope found after filtering. Original: {original_scopes}, Filtered: {filtered_scopes}")
            raise ValueError("Gmail connection does not have gmail.readonly scope. Please reconnect your Gmail account.")
        
        logger.info(f"Filtering scopes: {original_scopes} -> {filtered_scopes} (removed metadata, keeping readonly only)")
        
        # CRITICAL: Construct Credentials with ONLY gmail.readonly scope (never metadata)
        # Only include gmail.readonly and other non-Gmail scopes (openid, userinfo, etc.)
        readonly_only_scopes = [
            scope for scope in filtered_scopes
            if 'gmail.readonly' in scope or 'gmail' not in scope
        ]
        
        # Verify readonly is present
        if 'https://www.googleapis.com/auth/gmail.readonly' not in readonly_only_scopes:
            logger.error(f"ERROR: gmail.readonly not in filtered scopes. Filtered: {readonly_only_scopes}")
            raise ValueError("Gmail connection does not have gmail.readonly scope. Please reconnect.")
        
        logger.info(f"Creating Credentials with scopes: {readonly_only_scopes} (metadata excluded)")
        
        # Create credentials object with ONLY readonly scope (no metadata)
        credentials = Credentials(
            token=tokens_dict.get("token"),
            refresh_token=tokens_dict.get("refresh_token"),
            token_uri=tokens_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=tokens_dict.get("client_id"),
            client_secret=tokens_dict.get("client_secret"),
            scopes=readonly_only_scopes  # ONLY readonly scope, never metadata
        )
        
        # Refresh if expired - but preserve filtered scopes
        if credentials.expired and credentials.refresh_token:
            logger.info(f"Refreshing expired credentials...")
            original_refresh_scopes = credentials.scopes
            credentials.refresh(Request())
            # CRITICAL: After refresh, Google may return original scopes (including metadata)
            # We MUST filter them again to ensure metadata is not used
            if credentials.scopes != original_refresh_scopes:
                logger.warning(f"Scopes changed after refresh: {original_refresh_scopes} -> {credentials.scopes}")
                # Filter out metadata scope again - ONLY keep readonly
                refreshed_filtered = [
                    scope for scope in credentials.scopes
                    if 'gmail.metadata' not in scope
                ]
                # Verify readonly scope still exists
                if 'https://www.googleapis.com/auth/gmail.readonly' not in refreshed_filtered:
                    logger.error(f"ERROR: No readonly scope after refresh filtering. Filtered: {refreshed_filtered}")
                    raise ValueError("Gmail connection lost readonly scope after refresh. Please reconnect.")
                # Recreate credentials with filtered scopes (readonly only)
                credentials = Credentials(
                    token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    token_uri=credentials.token_uri,
                    client_id=credentials.client_id,
                    client_secret=credentials.client_secret,
                    scopes=refreshed_filtered  # Use filtered scopes (readonly only, no metadata)
                )
                logger.info(f"Filtered scopes after refresh: {credentials.scopes}")
            logger.info("Refreshed expired Gmail credentials")
        
        # CRITICAL: Verify token has ONLY readonly scope (required for full email format)
        logger.info(f"Verifying access token scopes with Google tokeninfo...")
        try:
            tokeninfo_result = await verify_token_scopes(credentials.token)
            has_readonly = tokeninfo_result.get("has_readonly", False)
            has_metadata = tokeninfo_result.get("has_metadata", False)
            tokeninfo_scopes = tokeninfo_result.get("scopes", [])
            
            logger.info(
                f"Token scopes: has_readonly={has_readonly}, "
                f"has_metadata={has_metadata}, "
                f"scopes={tokeninfo_scopes}"
            )
            
            # REJECT metadata scope - we need ONLY readonly for full email format
            if has_metadata:
                error_msg = (
                    "Gmail connection has metadata scope. "
                    "Metadata scope does not support full email format. "
                    "Please disconnect and reconnect your Gmail account to get ONLY readonly scope. "
                    f"Current token scopes: {tokeninfo_scopes}"
                )
                logger.error(f"❌ {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
            
            # REQUIRE readonly scope - required for full email format
            if not has_readonly:
                error_msg = (
                    "Gmail connection missing readonly scope. "
                    "Readonly scope is required for full email format. "
                    "Please disconnect and reconnect your Gmail account. "
                    f"Current token scopes: {tokeninfo_scopes}"
                )
                logger.error(error_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
            
            logger.info("✅ Token has readonly scope - full email format will be used")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Could not verify token scopes: {e}. Continuing with sync (assuming readonly scope)...")
        
        return credentials
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions (like 400 from token verification) - don't wrap them
        # This preserves the correct status code (400 for scope errors, etc.)
        raise http_exc
    except Exception as e:
        logger.error(f"Error getting Gmail credentials: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Gmail credentials: {str(e)}"
        )


async def fetch_emails_from_gmail(credentials: Credentials, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch emails from Gmail API.
    
    Supports both gmail.readonly (with search queries) and gmail.metadata (without queries).
    If only metadata scope is available, fetches all messages and filters in-memory.
    """
    try:
        # CRITICAL: Runtime verification - require ONLY readonly scope
        logger.info(f"Verifying access token before Gmail API call...")
        tokeninfo_result = await verify_token_scopes(credentials.token)
        has_readonly = tokeninfo_result.get("has_readonly", False)
        has_metadata = tokeninfo_result.get("has_metadata", False)
        tokeninfo_scopes = tokeninfo_result.get("scopes", [])
        
        logger.info(
            f"Tokeninfo verification: has_readonly={has_readonly}, "
            f"has_metadata={has_metadata}, scopes={tokeninfo_scopes}"
        )
        
        # REJECT metadata scope - we need ONLY readonly for full email format
        if has_metadata:
            error_msg = (
                "Gmail token has metadata scope. "
                "Metadata scope does not support full email format or search queries. "
                "Please disconnect and reconnect your Gmail account to get ONLY readonly scope. "
                f"Current token scopes: {tokeninfo_scopes}"
            )
            logger.error(f"❌ {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # REQUIRE readonly scope - required for full email format
        if not has_readonly:
            error_msg = (
                "Gmail connection missing readonly scope. "
                "Readonly scope is required for full email format. "
                "Please disconnect and reconnect your Gmail account. "
                f"Current token scopes: {tokeninfo_scopes}"
            )
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        logger.info("✅ Token has readonly scope - using search queries and full email format")
        
        service = build('gmail', 'v1', credentials=credentials)
        
        # Fetch the last N emails (most recent) without subject filtering
        # Just get the most recent emails in the inbox
        logger.info(f"Fetching last {max_results} emails (most recent) without subject filtering")
        
        # List messages without query filter - gets most recent emails
        results = service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        logger.info(f"Found {len(messages)} messages")
        
        # Fetch full message details (readonly scope supports 'full' format)
        email_data = []
        for msg in messages:
            try:
                # Use 'full' format - readonly scope supports full message content
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'  # readonly scope supports full message content
                ).execute()
                
                # Extract relevant data
                headers = message['payload'].get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), None)
                
                # Get snippet (available in full format)
                snippet = message.get('snippet', '')
                
                email_data.append({
                    'id': msg['id'],
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'snippet': snippet,
                    'raw': message  # Full message for processing
                })
            except Exception as e:
                logger.error(f"Error fetching message {msg.get('id')}: {e}")
                continue
        
        # Log the last email for debugging
        if email_data:
            last_email = email_data[-1]
            logger.info("=" * 80)
            logger.info("LAST EMAIL FETCHED:")
            logger.info(f"ID: {last_email.get('id')}")
            logger.info(f"Subject: {last_email.get('subject')}")
            logger.info(f"From: {last_email.get('from')}")
            logger.info(f"Date: {last_email.get('date')}")
            logger.info(f"Snippet: {last_email.get('snippet', '')[:100]}...")  # First 100 chars
            logger.info("=" * 80)
        
        return email_data
    except Exception as e:
        logger.error(f"Error fetching emails from Gmail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch emails: {str(e)}"
        )


def send_sse_message(message: str, progress: int = None, stage: str = None):
    """Format SSE message."""
    data = {"message": message}
    if progress is not None:
        data["progress"] = progress
    if stage is not None:
        data["stage"] = stage
    return f"data: {json.dumps(data)}\n\n"


async def sync_gmail_emails_streaming(
    user_id: str,
    access_token: str
):
    """Stream sync progress as SSE events."""
    try:
        yield send_sse_message("Starting email sync...", progress=5, stage="Initializing")
        await asyncio.sleep(0.1)
        
        # Step 1: Get Gmail credentials
        yield send_sse_message("Retrieving Gmail credentials...", progress=10, stage="Connecting")
        try:
            credentials = await get_gmail_credentials_async(user_id, access_token)
        except HTTPException as http_exc:
            # If it's a scope error (400), send clear message to user via SSE
            if http_exc.status_code == status.HTTP_400_BAD_REQUEST:
                error_detail = http_exc.detail or "Gmail connection has incorrect scopes"
                logger.error(f"Scope error during sync: {error_detail}")
                yield send_sse_message(
                    f"Error: {error_detail}. Please disconnect and reconnect Gmail in Settings.",
                    progress=0,
                    stage="Error"
                )
                return
            # Re-raise other HTTPExceptions (like 401, 500, etc.)
            raise
        
        # Verify scopes before proceeding
        scopes = credentials.scopes if credentials.scopes else []
        has_readonly_scope = 'https://www.googleapis.com/auth/gmail.readonly' in scopes
        
        logger.info(f"=== EMAIL SYNC SCOPE CHECK ===")
        logger.info(f"Available scopes (filtered): {scopes}")
        logger.info(f"Has gmail.readonly: {has_readonly_scope}")
        logger.info(f"==============================")
        
        # REQUIRED: Only readonly scope supports query parameter for searching
        # Metadata scope is filtered out in get_gmail_credentials_async
        if not has_readonly_scope:
            # No readonly scope - cannot use search queries
            error_msg = (
                "Gmail connection does not have readonly scope. "
                "Only gmail.readonly scope supports search queries (q parameter). "
                "Please disconnect and reconnect your Gmail account to get readonly scope."
            )
            logger.error(error_msg)
            yield send_sse_message(error_msg, progress=0, stage="Error")
            return
        
        yield send_sse_message("Gmail credentials retrieved successfully", progress=15, stage="Connected")
        await asyncio.sleep(0.1)
        
        # Step 2: Fetch emails from Gmail
        yield send_sse_message("Fetching emails from Gmail...", progress=20, stage="Fetching emails")
        # fetch_emails_from_gmail is now async, await it directly
        try:
            emails = await fetch_emails_from_gmail(credentials, 50)
            yield send_sse_message(f"Found {len(emails)} emails", progress=30, stage="Fetching emails")
            
            # Log the last email details
            if emails:
                last_email = emails[-1]
                logger.info("=" * 80)
                logger.info("LAST EMAIL IN SYNC:")
                logger.info(f"ID: {last_email.get('id')}")
                logger.info(f"Subject: {last_email.get('subject')}")
                logger.info(f"From: {last_email.get('from')}")
                logger.info(f"Date: {last_email.get('date')}")
                snippet = last_email.get('snippet', '')
                logger.info(f"Snippet: {snippet[:100]}{'...' if len(snippet) > 100 else ''}")
                logger.info("=" * 80)
        except HTTPException as e:
            # Check if it's a scope-related error
            error_detail = str(e.detail) if hasattr(e, 'detail') else str(e)
            if "403" in error_detail or "forbidden" in error_detail.lower() or "scope" in error_detail.lower():
                yield send_sse_message(
                    "Error: Gmail connection needs gmail.readonly scope for search queries. Please disconnect and reconnect your Gmail account.",
                    progress=0,
                    stage="Error"
                )
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            error_msg = str(e)
            if "scope" in error_msg.lower() or "403" in error_msg or "forbidden" in error_msg.lower():
                yield send_sse_message(
                    "Error: Gmail connection needs gmail.readonly scope for search queries. Please disconnect and reconnect your Gmail account in Settings.",
                    progress=0,
                    stage="Error"
                )
                return  # Stop syncing on scope error
            # Re-raise other exceptions
            raise
        await asyncio.sleep(0.1)
        
        if not emails:
            yield send_sse_message("No new emails found to process", progress=50, stage="No emails")
            # Update last_synced_at even if no emails
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{settings.AUTH_SERVICE_URL}/api/gmail/update-sync-time",
                        headers={"Authorization": f"Bearer {access_token}"},
                        json={"last_synced_at": datetime.utcnow().isoformat()},
                        timeout=5.0
                    )
            except Exception as e:
                logger.warning(f"Failed to update sync time: {e}")
            
            yield send_sse_message("Sync completed", progress=100, stage="Complete")
            return
        
        # Step 3: Process emails
        yield send_sse_message(f"Processing {len(emails)} emails...", progress=40, stage="Processing emails")
        processed_emails = []
        for idx, email in enumerate(emails):
            # Basic processing - extract company and role from subject/sender
            # This is a simplified version - in production, use AI service
            from email.utils import parsedate_to_datetime
            
            # Parse date
            try:
                received_at_dt = parsedate_to_datetime(email['date']) if email.get('date') else datetime.utcnow()
            except:
                received_at_dt = datetime.utcnow()
            
            # Extract company from email domain
            company_name = "Unknown"
            if '@' in email['from']:
                domain = email['from'].split('@')[1]
                # Remove common email providers
                if domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']:
                    company_name = domain.split('.')[0].title()
            
            # Extract role from subject (basic keyword matching)
            subject_lower = email['subject'].lower()
            role = email['subject'][:50]  # Use first 50 chars of subject as role
            
            # Determine status from subject keywords
            status = "applied"
            if any(word in subject_lower for word in ['rejected', 'declined', 'not selected']):
                status = "rejected"
            elif any(word in subject_lower for word in ['interview', 'screening', 'phone call']):
                status = "interview"
            elif any(word in subject_lower for word in ['offer', 'congratulations', 'selected']):
                status = "offer"
            
            processed_email = {
                "email_id": email['id'],
                "company_name": company_name,
                "role": role,
                "application_status": status,
                "confidence_score": 0.6,  # Basic extraction has lower confidence
                "received_at": received_at_dt.isoformat(),
                "summary": email.get('snippet', '')[:200]  # First 200 chars of snippet
            }
            processed_emails.append(processed_email)
            
            # Update progress during processing
            if (idx + 1) % 10 == 0 or idx == len(emails) - 1:
                progress_pct = 40 + int((idx + 1) / len(emails) * 30)
                yield send_sse_message(
                    f"Processed {idx + 1}/{len(emails)} emails...",
                    progress=progress_pct,
                    stage="Processing emails"
                )
                await asyncio.sleep(0.05)
        
        yield send_sse_message(f"Successfully processed {len(processed_emails)} emails", progress=70, stage="Processing emails")
        logger.info(f"Processed {len(processed_emails)} emails for user {user_id}")
        
        # Step 4: Send processed emails to application-service for ingestion
        yield send_sse_message("Sending processed emails to application service...", progress=75, stage="Updating Database")
        applications_created = 0
        try:
            async with httpx.AsyncClient() as client:
                # Format for application-service (matching ProcessedEmail schema)
                ingest_data = []
                for email in processed_emails:
                    from datetime import datetime
                    # received_at is already ISO format string from processing
                    received_at_str = email["received_at"]
                    try:
                        received_at_dt = datetime.fromisoformat(received_at_str.replace('Z', '+00:00'))
                    except:
                        received_at_dt = datetime.utcnow()
                    
                    ingest_data.append({
                        "email_id": email["email_id"],
                        "company_name": email["company_name"],
                        "role": email["role"],
                        "application_status": email["application_status"],
                        "confidence_score": email["confidence_score"],
                        "received_at": received_at_dt.isoformat(),
                        "summary": email.get("summary")
                    })
                
                response = await client.post(
                    f"{settings.APPLICATION_SERVICE_URL}/ingest/from-email-ai",
                    json=ingest_data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    applications_created = result.get("accepted", 0)
                    yield send_sse_message(
                        f"Created/updated {applications_created} job applications",
                        progress=90,
                        stage="Updating Database"
                    )
                    logger.info(f"Ingested {applications_created} applications for user {user_id}")
                else:
                    yield send_sse_message(
                        f"Warning: Failed to ingest some emails (Status: {response.status_code})",
                        progress=85,
                        stage="Updating Database"
                    )
                    logger.error(f"Failed to ingest emails: {response.status_code} - {response.text}")
        except Exception as e:
            yield send_sse_message(
                f"Error ingesting emails: {str(e)}",
                progress=85,
                stage="Error"
            )
            logger.error(f"Error ingesting emails to application-service: {e}", exc_info=True)
        
        # Step 5: Update last_synced_at
        yield send_sse_message("Updating sync timestamp...", progress=95, stage="Finalizing")
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{settings.AUTH_SERVICE_URL}/api/gmail/update-sync-time",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"last_synced_at": datetime.utcnow().isoformat()},
                    timeout=5.0
                )
        except Exception as e:
            logger.warning(f"Failed to update sync time: {e}")
        
        yield send_sse_message(
            f"Sync completed successfully! Processed {len(processed_emails)} emails, created {applications_created} applications",
            progress=100,
            stage="Complete"
        )
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error syncing emails for user {user_id}: {error_msg}", exc_info=True)
        yield send_sse_message(
            f"Error: {error_msg}",
            progress=0,
            stage="Error"
        )


@router.post("/gmail/sync")
async def sync_gmail_emails(
    user: dict = Depends(get_user_from_jwt),
    authorization: str = Header(None)
):
    """
    Sync emails from Gmail with real-time progress streaming via SSE.
    Fetches emails, processes them, and updates the database.
    """
    user_id = user.get("id")
    access_token = authorization.replace("Bearer ", "") if authorization else None
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID not found in token"
        )
    
    logger.info(f"Starting email sync for user {user_id}")
    
    return StreamingResponse(
        sync_gmail_emails_streaming(user_id, access_token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )
