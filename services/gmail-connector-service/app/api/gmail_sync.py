"""
Gmail email sync endpoint - fetches emails and processes them.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header
from fastapi.responses import StreamingResponse
from app.schemas.gmail import GmailConnectionStatus
from app.config import get_settings
from app.security.token_verification import verify_token_scopes
from app.security.google_oauth import refresh_access_token, ReauthRequiredError
from app.filters.query_builder import build_job_gmail_query
from app.services.email_classifier import classify_email, EmailCategory
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httpx
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import asyncio
import uuid

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
                error_detail = "Failed to get Gmail tokens"
                try:
                    error_data = response.json()
                    if "detail" in error_data:
                        error_detail = error_data["detail"]
                    elif "message" in error_data:
                        error_detail = error_data["message"]
                except:
                    error_text = response.text[:200] if hasattr(response, 'text') else str(response.status_code)
                    if error_text:
                        error_detail = f"Failed to get Gmail tokens: {error_text}"
                
                if response.status_code == 404:
                    error_detail = "Gmail account not connected. Please connect your Gmail account in Settings."
                elif response.status_code == 401:
                    error_detail = "Authentication failed. Please log in again."
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_detail
                )
            
            response_data = response.json()
            if "tokens" not in response_data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid response from auth service: 'tokens' key missing"
                )
            tokens_dict = response_data["tokens"]
        
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
        
        # Validate token exists
        access_token = tokens_dict.get("token")
        if not access_token:
            logger.error("Gmail access token is missing from auth-service response")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Gmail access token is missing. Please reconnect your Gmail account."
            )
        
        # Create credentials object with ONLY readonly scope (no metadata)
        credentials = Credentials(
            token=access_token,
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


async def _update_tokens_in_auth_service(user_id: str, access_token: str, new_access_token: str, new_refresh_token: str = None) -> None:
    """Update tokens in auth-service after refresh."""
    try:
        # Get current tokens
        async with httpx.AsyncClient() as client:
            get_response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/gmail/tokens",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0
            )
            if get_response.status_code != 200:
                logger.warning(f"Failed to get current tokens for update: {get_response.status_code}")
                return
            
            current_tokens = get_response.json()["tokens"]
            
            # Update access token
            current_tokens["token"] = new_access_token
            if new_refresh_token:
                current_tokens["refresh_token"] = new_refresh_token
            
            # Re-store updated tokens (create_or_update handles updates)
            tokens_json = json.dumps(current_tokens)
            gmail_email = current_tokens.get("gmail_email", "")
            
            store_response = await client.post(
                f"{settings.AUTH_SERVICE_URL}/api/gmail/store-tokens",
                json={
                    "tokens_json": tokens_json,
                    "gmail_email": gmail_email
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0
            )
            if store_response.status_code != 201:
                logger.warning(f"Failed to update tokens in auth-service: {store_response.status_code} - {store_response.text}")
            else:
                logger.info("Successfully updated tokens in auth-service after refresh")
    except Exception as e:
        logger.warning(f"Error updating tokens in auth-service: {e}")


async def fetch_emails_from_gmail(
    credentials: Credentials, 
    user_id: str,
    access_token: str,
    max_results: int = 50
) -> List[Dict[str, Any]]:
    """
    Fetch emails from Gmail API with proper token refresh handling.
    
    Stage 1: Uses strict Gmail query to only fetch likely job-related emails.
    Tokeninfo is optional debug only - Gmail API 401 is authoritative.
    """
    # Validate token exists
    if not credentials.token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail access token is missing. Please reconnect your Gmail account."
        )
    
    # Optional tokeninfo check (debug only, non-blocking)
    tokeninfo_success, tokeninfo_scopes = await verify_token_scopes(credentials.token)
    if tokeninfo_success:
        logger.debug(f"Tokeninfo scopes: {tokeninfo_scopes}")
    else:
        logger.debug("Tokeninfo check failed (non-blocking, continuing with Gmail API)")
    
    # Build strict Gmail query (Stage 1 pre-filter)
    query_days = getattr(settings, 'GMAIL_QUERY_DAYS', 180)
    search_query = build_job_gmail_query(days=query_days)
    max_results = min(max_results, getattr(settings, 'GMAIL_MAX_RESULTS', 50))
    
    logger.info(f"[STAGE 1] Gmail query: {search_query[:200]}...")
    logger.info(f"[STAGE 1] Max results: {max_results}")
    
    # Build Gmail service
    service = build('gmail', 'v1', credentials=credentials)
    
    # Attempt Gmail API call (with retry on 401)
    try:
        results = service.users().messages().list(
            userId='me',
            q=search_query,
            maxResults=max_results
        ).execute()
    except HttpError as e:
        # Gmail API returned error - check if 401 (unauthorized)
        if e.resp.status == 401:
            logger.warning("Gmail API returned 401 - attempting token refresh...")
            
            # Refresh token
            if not credentials.refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Re-auth required: Refresh token is missing. Please reconnect your Gmail account."
                )
            
            try:
                # Refresh using our async refresh function
                refresh_result = await refresh_access_token(credentials.refresh_token)
                
                # Update credentials
                credentials.token = refresh_result["access_token"]
                if refresh_result.get("expires_in"):
                    from datetime import timedelta
                    credentials.expiry = datetime.utcnow() + timedelta(seconds=refresh_result["expires_in"])
                
                # Update tokens in auth-service
                await _update_tokens_in_auth_service(
                    user_id=user_id,
                    access_token=access_token,
                    new_token=credentials.token,
                    refresh_token=credentials.refresh_token
                )
                
                # Rebuild service with new credentials
                service = build('gmail', 'v1', credentials=credentials)
                
                # Retry Gmail API call once
                logger.info("Token refreshed, retrying Gmail API call...")
                results = service.users().messages().list(
                    userId='me',
                    q=search_query,
                    maxResults=max_results
                ).execute()
                
            except ReauthRequiredError as reauth_error:
                logger.error(f"Token refresh failed: {reauth_error}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Re-auth required: {str(reauth_error)}"
                )
            except Exception as refresh_error:
                logger.error(f"Token refresh error: {refresh_error}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Re-auth required: Token refresh failed. Please reconnect your Gmail account."
                )
        else:
            # Non-401 error from Gmail API
            logger.error(f"Gmail API error: {e.resp.status} - {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY if e.resp.status >= 500 else status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Gmail API error: {str(e)}"
            )
    
    # Extract message IDs
    messages = results.get('messages', [])
    message_ids = [msg['id'] for msg in messages]
    
    logger.info(f"[STAGE 1] Found {len(message_ids)} messages from Gmail query")
    
    # Log example subjects (first 10) for sanity check
    if message_ids:
        logger.info(f"[STAGE 1] Example message IDs: {message_ids[:10]}")
    
    # Fetch full message details
    email_data = []
    for msg_id in message_ids:
        try:
            message = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            # Safely extract headers
            payload = message.get('payload', {}) if isinstance(message, dict) else {}
            headers_raw = payload.get('headers', []) if isinstance(payload, dict) else []
            
            # Ensure headers is a list
            if not isinstance(headers_raw, list):
                headers_raw = []
            
            # Extract header values safely
            headers = []
            for h in headers_raw:
                if isinstance(h, dict):
                    headers.append(h)
                else:
                    # Skip non-dict headers
                    continue
            
            subject = next((h.get('value', '') for h in headers if h.get('name', '') == 'Subject'), 'No Subject')
            sender = next((h.get('value', '') for h in headers if h.get('name', '') == 'From'), 'Unknown')
            date = next((h.get('value', '') for h in headers if h.get('name', '') == 'Date'), None)
            snippet = message.get('snippet', '') if isinstance(message, dict) else ''
            
            # Extract headers dict for classifier
            headers_dict = {h.get('name', ''): h.get('value', '') for h in headers if isinstance(h, dict) and h.get('name') and h.get('value')}
            
            email_data.append({
                'id': msg_id,
                'subject': subject,
                'from': sender,
                'date': date,
                'snippet': snippet,
                'headers': headers_dict,
                'raw': message
            })
            
        except HttpError as e:
            if e.resp.status == 401:
                # Token expired during fetch - would need another refresh
                logger.error(f"401 error fetching message {msg_id} - token expired during fetch")
                # Skip this message and continue
                continue
            else:
                logger.error(f"Error fetching message {msg_id}: {e.resp.status} - {str(e)}")
                continue
        except Exception as e:
            logger.error(f"Error fetching message {msg_id}: {e}", exc_info=True)
            continue
    
    logger.info(f"[STAGE 1] Successfully fetched {len(email_data)} messages")
    
    # Log example subjects
    if email_data:
        logger.info(f"[STAGE 1] Example subjects (first 10):")
        for email in email_data[:10]:
            logger.info(f"  - {email.get('subject', 'No Subject')[:80]}")
    
    return email_data


def send_sse_message(message: str, progress: int = None, stage: str = None, email_data: dict = None):
    """Format SSE message and return as bytes for streaming."""
    data = {"message": message}
    if progress is not None:
        data["progress"] = progress
    if stage is not None:
        data["stage"] = stage
    if email_data is not None:
        data["email_data"] = email_data
    sse_text = f"data: {json.dumps(data)}\n\n"
    # Return as bytes - FastAPI StreamingResponse handles bytes better for SSE
    return sse_text.encode('utf-8')


async def sync_gmail_emails_streaming(
    user_id: str,
    access_token: str
):
    """Stream sync progress as SSE events."""
    logger.info(f"[SYNC START] Beginning sync for user {user_id}")
    # Send first message IMMEDIATELY - before any async operations
    logger.info("[SYNC] Sending initial message: Starting email sync...")
    first_msg = send_sse_message("Starting email sync...", progress=5, stage="Initializing")
    logger.info(f"[SYNC] Message bytes length: {len(first_msg)}")
    yield first_msg
    logger.info("[SYNC] Initial message yielded - generator is active")
    
    try:
        # Small delay to allow message to flush
        await asyncio.sleep(0.1)
        
        # Step 1: Get Gmail credentials
        yield send_sse_message("Retrieving Gmail credentials...", progress=10, stage="Connecting")
        try:
            credentials = await get_gmail_credentials_async(user_id, access_token)
        except ValueError as ve:
            # Handle ValueError (e.g., missing readonly scope)
            error_detail = str(ve)
            logger.error(f"Gmail credentials error: {error_detail}")
            yield send_sse_message(
                f"Error: {error_detail}. Please disconnect and reconnect Gmail in Settings.",
                progress=0,
                stage="Error"
            )
            return
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
            # For 401 (unauthorized), send clear message
            if http_exc.status_code == status.HTTP_401_UNAUTHORIZED:
                error_detail = http_exc.detail or "Gmail connection expired. Please reconnect."
                logger.error(f"Auth error during sync: {error_detail}")
                yield send_sse_message(
                    f"Error: {error_detail} Please disconnect and reconnect Gmail in Settings.",
                    progress=0,
                    stage="Error"
                )
                return
            # Re-raise other HTTPExceptions (like 500, etc.)
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
        
        # Step 2: Fetch emails from Gmail (Stage 1 - strict query)
        yield send_sse_message("Fetching job-related emails from Gmail...", progress=20, stage="Fetching emails")
        try:
            max_results = getattr(settings, 'GMAIL_MAX_RESULTS', 50)
            emails = await fetch_emails_from_gmail(credentials, user_id, access_token, max_results)
            yield send_sse_message(f"Found {len(emails)} emails from Gmail query", progress=30, stage="Fetching emails")
            
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
            yield send_sse_message("No job application emails found", progress=50, stage="No emails")
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
        
        # Step 3: Stage 2 - Strict classification (deterministic rules, not AI)
        yield send_sse_message(f"Classifying {len(emails)} emails with strict rules...", progress=40, stage="Classifying emails")
        processed_emails = []
        filtered_count = 0
        category_counts = {}
        min_confidence = getattr(settings, 'CLASSIFIER_MIN_CONFIDENCE', 0.85)
        store_categories_str = getattr(settings, 'STORE_CATEGORIES', "APPLIED_CONFIRMATION,INTERVIEW,REJECTION,OFFER")
        store_categories = [cat.strip() for cat in store_categories_str.split(',')]
        
        for email in emails:
            try:
                # Validate email is a dict
                if not isinstance(email, dict):
                    logger.error(f"Email is not a dict, type: {type(email)}, value: {str(email)[:100]}")
                    continue
                
                msg_id = email.get('id', 'unknown')
                subject = email.get('subject', '') or ''
                from_email = email.get('from', '') or ''
                snippet = email.get('snippet', '') or ''
                
                # Ensure headers is always a list of dicts
                headers_raw = email.get('headers', {})
                if isinstance(headers_raw, dict):
                    # Convert dict to list of {name, value} dicts
                    headers = [{"name": str(k), "value": str(v)} for k, v in headers_raw.items() if k and v]
                elif isinstance(headers_raw, list):
                    # Filter to only dict items and ensure they have name/value
                    headers = [
                        {"name": str(h.get('name', '')), "value": str(h.get('value', ''))} 
                        for h in headers_raw 
                        if isinstance(h, dict) and h.get('name') and h.get('value')
                    ]
                elif isinstance(headers_raw, str):
                    # If it's a string, create empty list (can't parse string headers)
                    headers = []
                else:
                    headers = []
                
                # Extract body text if needed (only for medium confidence)
                body_text = None
                raw_message = email.get('raw', {})
                if raw_message and isinstance(raw_message, dict):
                    # Extract plain text body from raw message
                    try:
                        payload = raw_message.get('payload', {})
                        if isinstance(payload, dict) and 'parts' in payload:
                            parts = payload.get('parts', [])
                            if isinstance(parts, list):
                                for part in parts:
                                    if isinstance(part, dict) and part.get('mimeType') == 'text/plain':
                                        import base64
                                        body_obj = part.get('body', {})
                                        if isinstance(body_obj, dict):
                                            data = body_obj.get('data', '')
                                            if data and isinstance(data, str):
                                                body_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore').lower()
                                                break
                        # Also check for single-part messages
                        elif isinstance(payload, dict) and payload.get('mimeType') == 'text/plain':
                            import base64
                            body_obj = payload.get('body', {})
                            if isinstance(body_obj, dict):
                                data = body_obj.get('data', '')
                                if data and isinstance(data, str):
                                    body_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore').lower()
                    except Exception as e:
                        logger.debug(f"Error extracting body text for email {msg_id[:20]}: {e}")
                        pass
                
                # Prepare email data for classifier
                email_data = {
                    'subject': subject,
                    'from': from_email,
                    'snippet': snippet,
                    'headers': headers,
                    'body_text': body_text or snippet  # Use snippet as fallback
                }
                
                # Classify email (Stage 2)
                try:
                    classification = classify_email(email_data)
                    label = classification.get('label', 'OTHER')
                    confidence = classification.get('confidence', 0.0)
                    reasons = classification.get('reasons', [])
                    stored = classification.get('stored', False)
                    discard_reason = classification.get('discard_reason', '')
                except Exception as e:
                    logger.error(f"Error classifying email {msg_id[:20]}: {e}", exc_info=True)
                    # Default to OTHER/not stored on classification error
                    label = 'OTHER'
                    confidence = 0.0
                    reasons = [f"Classification error: {str(e)}"]
                    stored = False
                    discard_reason = f"Classification failed: {str(e)}"
                
                # Update category counts
                category_counts[label] = category_counts.get(label, 0) + 1
                
                # STRUCTURED LOGGING (mandatory per email)
                log_data = {
                    "msg_id": msg_id[:20],
                    "from": from_email[:50],
                    "subject": subject[:80],
                    "score": int(confidence * 100) if confidence else 0,
                    "allow_hits": reasons if stored else [],
                    "deny_hits": reasons if not stored else [],
                    "category": label,
                    "stored": stored
                }
                logger.info(f"[STAGE 2] {json.dumps(log_data)}")
                
                # Only store if confidence >= 0.85 AND label is in store_categories
                if not stored or confidence < min_confidence or label not in store_categories:
                    filtered_count += 1
                    if label == 'OTHER':
                        logger.info(f"[STAGE 2] msg={msg_id[:20]} SKIPPED: {discard_reason or 'Label=OTHER'}")
                    else:
                        logger.info(f"[STAGE 2] msg={msg_id[:20]} SKIPPED: confidence {confidence:.2f} < {min_confidence} or label {label} not in store_categories")
                    continue
                
                # Extract date
                date_str = email.get('date')
                from email.utils import parsedate_to_datetime
                try:
                    received_at_dt = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()
                except:
                    received_at_dt = datetime.utcnow()
                
                # Extract company from sender domain
                company_name = ""
                if '@' in from_email:
                    domain = from_email.split('@')[1]
                    if domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']:
                        company_name = domain.split('.')[0].title()
                
                # Use role from subject
                role = subject[:50] if subject else ""
                
                # Map classifier label to application status
                status_map = {
                    'APPLIED_CONFIRMATION': 'Applied',
                    'INTERVIEW': 'Interview',
                    'REJECTION': 'Rejected',
                    'OFFER': 'Accepted/Offer',
                    'ASSESSMENT': 'Interview',  # Assessment is part of interview process
                    'RECRUITER_OUTREACH': 'Applied'  # Outreach might lead to application
                }
                application_status = status_map.get(label, 'Applied')
                
                processed_email = {
                    "email_id": msg_id,
                    "company_name": company_name,
                    "role": role,
                    "application_status": application_status,
                    "confidence_score": confidence,
                    "received_at": received_at_dt.isoformat(),
                    "summary": snippet[:200] if snippet else ""
                }
                processed_emails.append(processed_email)
                
                logger.info(f"[STAGE 2] msg={msg_id[:20]} STORED: label={label} confidence={confidence:.2f}")
                
                # Send real-time update for each email stored
                yield send_sse_message(
                    f"✓ Stored: {company_name} - {role} ({application_status})",
                    progress=min(70, 40 + int((len(processed_emails) / max(len(emails), 1)) * 30)),
                    stage="Classifying emails",
                    email_data={
                        "company_name": company_name,
                        "role": role,
                        "status": application_status,
                        "count": len(processed_emails)
                    }
                )
                await asyncio.sleep(0.05)  # Small delay to show step-by-step
            except Exception as e:
                logger.error(f"Error processing email {email.get('id', 'unknown')[:20] if isinstance(email, dict) else 'unknown'}: {e}", exc_info=True)
                # Continue with next email
                continue
        
        # Log totals
        logger.info(f"[STAGE 2] TOTALS: fetched={len(emails)}, classified_by_category={category_counts}, stored={len(processed_emails)}, skipped={filtered_count}")
        
        # Update progress
        yield send_sse_message(
            f"Classified {len(emails)} emails: {len(processed_emails)} stored, {filtered_count} skipped",
            progress=70,
            stage="Classifying emails"
        )
        await asyncio.sleep(0.1)
        
        if not processed_emails:
            yield send_sse_message(
                f"No job application emails to store after classification (skipped {filtered_count})",
                progress=95,
                stage="No emails to store"
            )
            # Update last_synced_at even if no emails stored
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
        
        # Create summary
        status_counts = {}
        for email in processed_emails:
            status = email.get("application_status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        status_summary = ", ".join([f"{count} {status}" for status, count in sorted(status_counts.items())])
        
        yield send_sse_message(
            f"Sync completed! Stored {len(processed_emails)} job application emails ({status_summary}). Created/updated {applications_created} applications.",
            progress=100,
            stage="Complete"
        )
        
    except HTTPException as http_exc:
        error_msg = str(http_exc.detail) if hasattr(http_exc, 'detail') else str(http_exc)
        logger.error(f"HTTP error syncing emails for user {user_id}: {error_msg}", exc_info=True)
        yield send_sse_message(
            f"Error: {error_msg}",
            progress=0,
            stage="Error"
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
    
    # Create the generator
    generator = sync_gmail_emails_streaming(user_id, access_token)
    logger.info(f"Generator created for user {user_id}")
    
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )
