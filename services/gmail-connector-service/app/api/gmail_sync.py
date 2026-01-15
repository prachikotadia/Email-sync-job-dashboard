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
from app.services.strict_classifier import classify_email_strict
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httpx
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple
import asyncio
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

# Per-user sync lock (in-memory). Prevents concurrent syncs for same user.
_ACTIVE_GMAIL_SYNCS = set()
_ACTIVE_GMAIL_SYNCS_LOCK = asyncio.Lock()


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
    max_results: int = None,
    last_synced_date: str = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    PRODUCTION-GRADE Gmail email fetcher with proper pagination.
    
    Requirements:
    - Fetches in batches of 100 (configurable)
    - Hard limit of 1200 emails per sync
    - Sorted by internalDate DESC (newest first)
    - Two-stage filtering (Stage 1: Gmail query, Stage 2: Classification)
    - Full email content extraction (subject, from, to, snippet, plain text, HTML)
    - Incremental sync support (only fetch newer emails)
    """
    # Validate token exists
    if not credentials.token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gmail access token is missing. Please reconnect your Gmail account."
        )
    
    # Get configuration
    batch_size = getattr(settings, 'GMAIL_BATCH_SIZE', 100)
    hard_limit = getattr(settings, 'GMAIL_MAX_RESULTS', 1200)
    max_results = min(max_results or hard_limit, hard_limit)  # Enforce hard limit
    
    # Build Stage 1 Gmail query (fast pre-filter)
    query_days = getattr(settings, 'GMAIL_QUERY_DAYS', 180)
    search_query = build_job_gmail_query(days=query_days, last_synced_date=last_synced_date)
    
    logger.info(f"[STAGE 1] Gmail query: {search_query[:200]}...")
    logger.info(f"[STAGE 1] Batch size: {batch_size}, Hard limit: {hard_limit}, Max results: {max_results}")
    logger.info(f"[STAGE 1] Incremental sync: {last_synced_date is not None}")
    
    # Build Gmail service
    service = build('gmail', 'v1', credentials=credentials)
    
    # RULE 1: PRODUCTION-GRADE PAGINATION - Fetch in batches of 100, up to hard limit
    all_message_ids = []
    all_message_metadata = []  # Store (id, internalDate) for sorting
    page_token = None
    fetched_count = 0
    pages_fetched = 0  # RULE 1: Track pages fetched
    
    try:
        while fetched_count < max_results:
            # Calculate batch size for this request
            remaining = max_results - fetched_count
            current_batch_size = min(batch_size, remaining)
            
            request_params = {
                'userId': 'me',
                'q': search_query,
                'maxResults': current_batch_size
                # Gmail API returns messages in reverse chronological order (newest first) by default
                # This is what we want - most recent emails first
            }
            if page_token:
                request_params['pageToken'] = page_token
            
            results = service.users().messages().list(**request_params).execute()
            messages = results.get('messages', [])
            
            if not messages:
                logger.info(f"[STAGE 1] No more messages found")
                break
            
            # Store message IDs and fetch metadata for sorting
            for msg in messages:
                msg_id = msg.get('id')
                if msg_id:
                    all_message_ids.append(msg_id)
                    # We'll get internalDate when fetching full message
                    all_message_metadata.append({'id': msg_id})
            
            fetched_count = len(all_message_ids)
            pages_fetched += 1  # RULE 1: Increment page count
            logger.info(f"[STAGE 1] Fetched page {pages_fetched}: {len(messages)} messages (total: {fetched_count}/{max_results})")
            
            page_token = results.get('nextPageToken')
            if not page_token:
                logger.info(f"[STAGE 1] No more pages available")
                break  # No more pages
            
            # Enforce hard limit
            if fetched_count >= max_results:
                logger.info(f"[STAGE 1] Reached hard limit of {max_results} emails")
                break
        
        # RULE 1: Log pagination stats
        logger.info(f"[STAGE 1] ✅ Pagination complete: Fetched {len(all_message_ids)} message IDs across {pages_fetched} pages")
        logger.info(f"[STAGE 1] Processing {len(all_message_ids)} most recent emails (sorted by internalDate DESC)")
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
                
                # Retry Gmail API call with pagination
                logger.info("Token refreshed, retrying Gmail API call with pagination...")
                all_message_ids = []
                page_token = None
                while len(all_message_ids) < max_results:
                    request_params = {
                        'userId': 'me',
                        'q': search_query,
                        'maxResults': min(500, max_results - len(all_message_ids))
                    }
                    if page_token:
                        request_params['pageToken'] = page_token
                    
                    results = service.users().messages().list(**request_params).execute()
                    messages = results.get('messages', [])
                    all_message_ids.extend([msg['id'] for msg in messages])
                    
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break
                
                message_ids = all_message_ids[:max_results]
                
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
    
        # Sort by internalDate DESC (newest first) - Gmail API already returns newest first, but we'll verify
        # We'll sort after fetching full messages to get internalDate
        
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
                
                # Retry Gmail API call with pagination
                logger.info("Token refreshed, retrying Gmail API call with pagination...")
                all_message_ids = []
                all_message_metadata = []
                page_token = None
                fetched_count = 0
                
                while fetched_count < max_results:
                    remaining = max_results - fetched_count
                    current_batch_size = min(batch_size, remaining)
                    
                    request_params = {
                        'userId': 'me',
                        'q': search_query,
                        'maxResults': current_batch_size
                    }
                    if page_token:
                        request_params['pageToken'] = page_token
                    
                    results = service.users().messages().list(**request_params).execute()
                    messages = results.get('messages', [])
                    
                    if not messages:
                        break
                    
                    for msg in messages:
                        msg_id = msg.get('id')
                        if msg_id:
                            all_message_ids.append(msg_id)
                            all_message_metadata.append({'id': msg_id})
                    
                    fetched_count = len(all_message_ids)
                    page_token = results.get('nextPageToken')
                    if not page_token or fetched_count >= max_results:
                        break
                
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
    
    logger.info(f"[STAGE 1] ✅ Found {len(all_message_ids)} messages from Gmail query")
    
    # STAGE 2: Fetch FULL email content for each message
    logger.info(f"[STAGE 2] Fetching full email content for {len(all_message_ids)} messages...")
    email_data = []
    import base64
    import html2text
    
    for idx, msg_id in enumerate(all_message_ids, 1):
        try:
            # Fetch full message with all parts
            message = service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            # Extract internalDate for sorting (newest first)
            internal_date = message.get('internalDate')
            internal_date_int = int(internal_date) if internal_date else 0
            
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
            
            subject = next((h.get('value', '') for h in headers if h.get('name', '') == 'Subject'), 'No Subject')
            sender = next((h.get('value', '') for h in headers if h.get('name', '') == 'From'), 'Unknown')
            to_email = next((h.get('value', '') for h in headers if h.get('name', '') == 'To'), '')
            date = next((h.get('value', '') for h in headers if h.get('name', '') == 'Date'), None)
            snippet = message.get('snippet', '') if isinstance(message, dict) else ''
            
            # Extract headers dict for classifier
            headers_dict = {h.get('name', ''): h.get('value', '') for h in headers if isinstance(h, dict) and h.get('name') and h.get('value')}
            
            # FULL EMAIL CONTENT EXTRACTION (Stage 2 requirement)
            plain_text_body = ''
            html_body = ''
            
            def extract_body_from_parts(parts):
                """Recursively extract body from message parts."""
                plain_text = ''
                html = ''
                
                for part in parts:
                    mime_type = part.get('mimeType', '')
                    body_data = part.get('body', {}).get('data', '')
                    
                    if mime_type == 'text/plain' and body_data and not plain_text:
                        try:
                            plain_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                        except:
                            pass
                    elif mime_type == 'text/html' and body_data and not html:
                        try:
                            html = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                        except:
                            pass
                    
                    # Recursively check nested parts
                    if 'parts' in part:
                        nested_plain, nested_html = extract_body_from_parts(part['parts'])
                        if nested_plain and not plain_text:
                            plain_text = nested_plain
                        if nested_html and not html:
                            html = nested_html
                
                return plain_text, html
            
            # Extract body from payload
            if 'parts' in payload:
                plain_text_body, html_body = extract_body_from_parts(payload['parts'])
            elif payload.get('mimeType') == 'text/plain':
                body_data = payload.get('body', {}).get('data', '')
                if body_data:
                    try:
                        plain_text_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                    except:
                        pass
            elif payload.get('mimeType') == 'text/html':
                body_data = payload.get('body', {}).get('data', '')
                if body_data:
                    try:
                        html_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                        # Convert HTML to plain text
                        plain_text_body = html2text.html2text(html_body)
                    except:
                        pass
            
            # Use plain text body, fallback to snippet
            body_text = plain_text_body or snippet
            
            email_data.append({
                'id': msg_id,
                'thread_id': message.get('threadId', ''),
                'internal_date': internal_date_int,
                'subject': subject,
                'from': sender,
                'to': to_email,
                'date': date,
                'snippet': snippet,
                'plain_text_body': plain_text_body,
                'html_body': html_body,
                'body_text': body_text,
                'headers': headers_dict,
                'raw': message
            })
            
            # Log progress every 50 emails
            if idx % 50 == 0:
                logger.info(f"[STAGE 2] Fetched {idx}/{len(all_message_ids)} emails...")
            
        except HttpError as e:
            if e.resp.status == 401:
                logger.error(f"401 error fetching message {msg_id} - token expired during fetch")
                continue
            else:
                logger.error(f"Error fetching message {msg_id}: {e.resp.status} - {str(e)}")
                continue
        except Exception as e:
            logger.error(f"Error fetching message {msg_id}: {e}", exc_info=True)
            continue
    
    # REQUIREMENT 1: Strict reverse chronological order (newest → oldest)
    # Sort by internalDate DESC to ensure most recent emails are processed first
    email_data.sort(key=lambda x: x.get('internal_date', 0), reverse=True)
    logger.info(f"[REQUIREMENT 1] ✅ Sorted {len(email_data)} emails by internalDate DESC (newest first)")
    
    logger.info(f"[STAGE 2] ✅ Successfully fetched and extracted {len(email_data)} full email messages")
    logger.info(f"[STAGE 2] Emails sorted by internalDate DESC (newest first)")
    
    # Log example subjects (first 10) for debugging
    if email_data:
        logger.info(f"[STAGE 2] Example subjects (first 10, newest first):")
        for email in email_data[:10]:
            logger.info(f"  - [{email.get('internal_date', 0)}] {email.get('subject', 'No Subject')[:80]}")
    
    return email_data, pages_fetched


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
        
        # Step 2: Get last sync info for incremental sync (graceful degradation if endpoint doesn't exist)
        last_synced_date = None
        last_message_internal_date = None
        try:
            async with httpx.AsyncClient() as client:
                # Try to get last sync info (endpoint may not exist yet)
                sync_info_response = await client.get(
                    f"{settings.AUTH_SERVICE_URL}/api/gmail/sync-info",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=5.0
                )
                if sync_info_response.status_code == 200:
                    sync_info = sync_info_response.json()
                    last_synced_date = sync_info.get('last_synced_at')
                    last_message_internal_date = sync_info.get('last_message_internal_date')
                    logger.info(f"[INCREMENTAL SYNC] Last sync: {last_synced_date}, Last message date: {last_message_internal_date}")
                else:
                    logger.info(f"[INCREMENTAL SYNC] Sync-info endpoint returned {sync_info_response.status_code}, doing full sync")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"[INCREMENTAL SYNC] Sync-info endpoint not found (404), doing full sync")
            else:
                logger.warning(f"Could not fetch last sync info (will do full sync): {e}")
        except Exception as e:
            logger.warning(f"Could not fetch last sync info (will do full sync): {e}")
        
        # Step 3: Fetch emails from Gmail (Stage 1 - Gmail API query + Stage 2 - Full content extraction)
        yield send_sse_message("Fetching job-related emails from Gmail...", progress=20, stage="Fetching emails")
        try:
            max_results = getattr(settings, 'GMAIL_MAX_RESULTS', 1200)
            emails, pages_fetched = await fetch_emails_from_gmail(
                credentials, 
                user_id, 
                access_token, 
                max_results=max_results,
                last_synced_date=last_synced_date
            )
            
            total_scanned = len(emails)
            logger.info(f"[SYNC STATS] Total emails scanned: {total_scanned}")
            logger.info(f"[SYNC STATS] Pages fetched: {pages_fetched}")
            yield send_sse_message(f"Scanned {total_scanned} emails from Gmail", progress=30, stage="Fetching emails")
            
            # Log the most recent email details (first in sorted list)
            if emails:
                most_recent = emails[0]  # First email is newest (sorted DESC)
                logger.info("=" * 80)
                logger.info("MOST RECENT EMAIL IN SYNC:")
                logger.info(f"ID: {most_recent.get('id')}")
                logger.info(f"Internal Date: {most_recent.get('internal_date')}")
                logger.info(f"Subject: {most_recent.get('subject')}")
                logger.info(f"From: {most_recent.get('from')}")
                logger.info(f"Date: {most_recent.get('date')}")
                snippet = most_recent.get('snippet', '')
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
        
        # STEP 1: STORE ALL RAW EMAILS FIRST (NO CLASSIFICATION)
        yield send_sse_message(f"Storing {len(emails)} raw emails...", progress=30, stage="Storing raw emails")
        logger.info(f"[STEP 1] Storing {len(emails)} raw emails (NO CLASSIFICATION)")
        
        raw_emails_stored = []
        for idx, email in enumerate(emails, 1):
            try:
                if not isinstance(email, dict):
                    continue
                
                msg_id = email.get('id', f'unknown_{idx}')
                subject = email.get('subject', '') or ''
                from_email = email.get('from', '') or ''
                snippet = email.get('snippet', '') or ''
                body_text = email.get('body_text', '') or snippet
                
                # Extract date
                internal_date = email.get('internal_date')
                if internal_date:
                    from datetime import datetime as dt
                    received_at_dt = dt.fromtimestamp(internal_date / 1000)
                else:
                    date_str = email.get('date')
                    from email.utils import parsedate_to_datetime
                    try:
                        received_at_dt = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()
                    except:
                        received_at_dt = datetime.utcnow()
                
                # Store raw email data (NO CLASSIFICATION)
                raw_email = {
                    "email_id": msg_id,
                    "thread_id": email.get('thread_id', ''),
                    "subject": subject,
                    "from_email": from_email,
                    "to_email": email.get('to', ''),
                    "snippet": snippet,
                    "body_text": body_text[:10000] if body_text else None,
                    "received_at": received_at_dt.isoformat(),
                    "internal_date": email.get('internal_date', 0),
                }
                raw_emails_stored.append(raw_email)
                
                if idx % 100 == 0:
                    logger.info(f"[STEP 1] Stored {idx}/{len(emails)} raw emails")
            except Exception as e:
                logger.error(f"Error storing raw email {idx}: {e}", exc_info=True)
                continue
        
        logger.info(f"[STEP 1] ✅ Stored {len(raw_emails_stored)} raw emails")
        logger.info(f"📊 [DATA FLOW] Fetched: {len(emails)} emails from Gmail")
        logger.info(f"📊 [DATA FLOW] Stored: {len(raw_emails_stored)} raw emails in memory")
        logger.info(f"📊 [DATA FLOW] NO LIMIT on storage - ALL emails stored")
        
        # STEP 2: CLASSIFY ALL STORED EMAILS
        yield send_sse_message(f"Classifying {len(raw_emails_stored)} emails...", progress=50, stage="Classifying emails")
        logger.info(f"[STEP 2] Classifying {len(raw_emails_stored)} stored emails")
        
        processed_emails = []
        from app.services.job_email_classifier import classify_job_email, JobStatus
        from app.services.email_cleaner import clean_email_body
        
        # Status counters for comprehensive logging (ALL statuses)
        status_counts = {
            'APPLIED': 0,
            'APPLICATION_RECEIVED': 0,
            'REJECTED': 0,
            'INTERVIEW': 0,
            'OFFER': 0,
            'ACCEPTED': 0,
            'WITHDRAWN': 0,
            'ASSESSMENT': 0,
            'SCREENING': 0,
            'FOLLOW_UP': 0,
            'OTHER_JOB_RELATED': 0,  # DEFAULT for uncertain
            'NON_JOB': 0,
        }
        
        # Process each RAW email (already stored, now classify)
        logger.info(f"[STEP 2] Starting classification of {len(raw_emails_stored)} raw emails")
        
        for idx, raw_email in enumerate(raw_emails_stored, 1):
            # Initialize defaults (will be set below)
            msg_id = raw_email.get('email_id', f'unknown_{idx}')
            subject = raw_email.get('subject', '') or ''
            from_email = raw_email.get('from_email', '') or ''
            snippet = raw_email.get('snippet', '') or ''
            body_text = raw_email.get('body_text', '') or snippet
            received_at_str = raw_email.get('received_at', '')
            internal_date = raw_email.get('internal_date', 0)
            status = JobStatus.OTHER_JOB_RELATED
            confidence = 0.5
            confidence_str = 'low'
            reason = 'Processing'
            company_name = 'UNKNOWN'
            role = ""
            
            try:
                # Parse received_at
                try:
                    from datetime import datetime as dt
                    received_at_dt = dt.fromisoformat(received_at_str.replace('Z', '+00:00'))
                except:
                    from datetime import datetime as dt
                    received_at_dt = dt.utcnow()
                
                # Clean email body
                if body_text:
                    try:
                        body_text = clean_email_body(body_text)
                    except:
                        pass  # Keep original if cleaning fails
                
                # If body is empty → use snippet or subject as fallback
                if not body_text or len(body_text.strip()) < 10:
                    body_text = snippet or subject or 'No content'
                
                # Prepare email data for classifier
                email_data = {
                    'id': msg_id,
                    'subject': subject,
                    'from': from_email,
                    'to': raw_email.get('to_email', ''),
                    'snippet': snippet,
                    'body_text': body_text
                }
                
                # CLASSIFY (VERY PERMISSIVE) - ALL emails already stored, now just classify
                try:
                    classification = classify_job_email(email_data)
                    status = classification.get('status', JobStatus.OTHER_JOB_RELATED)
                    confidence_str = classification.get('confidence', 'low')
                    reason = classification.get('reason', 'Classified')
                    company_name = classification.get('company', 'UNKNOWN')
                    
                    # Convert confidence string to float
                    confidence_map = {'high': 0.9, 'medium': 0.7, 'low': 0.5}
                    confidence = confidence_map.get(confidence_str, 0.5)
                    
                    # Update status counts (use .value to get string)
                    status_key = status.value if hasattr(status, 'value') else str(status)
                    status_counts[status_key] = status_counts.get(status_key, 0) + 1
                    
                    if idx <= 5 or idx % 100 == 0:  # Log first 5 and every 100th
                        logger.info(f"[CLASSIFY] [{idx}/{len(raw_emails_stored)}] email_id={msg_id[:20]} subject='{subject[:60]}' status={status_key} company={company_name}")
                    
                except Exception as e:
                    logger.error(f"Error classifying email {msg_id[:20]}: {e}", exc_info=True)
                    # Default to OTHER_JOB_RELATED on error
                    status = JobStatus.OTHER_JOB_RELATED
                    confidence = 0.5
                    confidence_str = 'low'
                    reason = f"Classification error: {str(e)[:100]}"
                    company_name = 'UNKNOWN'
                    status_counts['OTHER_JOB_RELATED'] += 1
                
                # DO NOT fail if company is UNKNOWN
                if not company_name or company_name == '':
                    company_name = "UNKNOWN"
                
                # Extract role from subject
                if subject:
                    try:
                        import re
                        role_patterns = [
                            r'(?:for|position|role|as)\s+([A-Z][a-zA-Z\s]+(?:Engineer|Manager|Developer|Designer|Analyst|Specialist|Lead|Director))',
                            r'([A-Z][a-zA-Z\s]+(?:Engineer|Manager|Developer|Designer|Analyst|Specialist|Lead|Director))',
                        ]
                        for pattern in role_patterns:
                            match = re.search(pattern, subject, re.IGNORECASE)
                            if match:
                                role = match.group(1).strip()[:50]
                                break
                        if not role:
                            role = subject.split('-')[0].split(':')[0].strip()[:50]
                    except:
                        role = subject[:50]  # Fallback to first 50 chars
                
                # Map JobStatus to application status
                status_map = {
                    JobStatus.APPLIED: 'APPLIED',
                    JobStatus.APPLICATION_RECEIVED: 'APPLICATION_RECEIVED',
                    JobStatus.INTERVIEW: 'INTERVIEW',
                    JobStatus.REJECTED: 'REJECTED',
                    JobStatus.ASSESSMENT: 'ASSESSMENT',
                    JobStatus.SCREENING: 'SCREENING',
                    JobStatus.OFFER: 'OFFER',
                    JobStatus.ACCEPTED: 'ACCEPTED',
                    JobStatus.WITHDRAWN: 'WITHDRAWN',
                    JobStatus.FOLLOW_UP: 'FOLLOW_UP',
                    JobStatus.OTHER_JOB_RELATED: 'OTHER_JOB_RELATED',
                    JobStatus.NON_JOB: 'NON_JOB',
                }
                application_status = status_map.get(status, 'OTHER_JOB_RELATED')
                
            except Exception as e:
                # If anything fails before classification, use defaults
                logger.error(f"Error processing raw email {idx} (before classification): {e}", exc_info=True)
                try:
                    received_at_dt = datetime.fromisoformat(received_at_str.replace('Z', '+00:00')) if received_at_str else datetime.utcnow()
                except:
                    received_at_dt = datetime.utcnow()
                application_status = 'OTHER_JOB_RELATED'
                status_counts['OTHER_JOB_RELATED'] += 1
            
            # ALWAYS create processed email (even if classification failed)
            try:
                processed_email = {
                    "email_id": msg_id,
                    "thread_id": raw_email.get('thread_id', ''),
                    "internal_date": internal_date,
                    "company_name": company_name,
                    "role": role,
                    "application_status": application_status,
                    "confidence_score": confidence,
                    "received_at": received_at_dt.isoformat(),
                    "summary": snippet[:200] if snippet else "",
                    "from_email": from_email,
                    "to_email": raw_email.get('to_email', ''),
                    "body_text": body_text[:10000] if body_text else None,
                    "subject": subject
                }
                processed_emails.append(processed_email)
                
                # Log progress
                if idx % 100 == 0:
                    logger.info(f"[STEP 2] Classified {idx}/{len(raw_emails_stored)} emails (processed_emails count: {len(processed_emails)})")
                
                # Send real-time update
                if len(processed_emails) % 50 == 0:
                    yield send_sse_message(
                        f"✓ Classified {len(processed_emails)}/{len(raw_emails_stored)} emails",
                        progress=min(70, 50 + int((len(processed_emails) / max(len(raw_emails_stored), 1)) * 20)),
                        stage="Classifying emails",
                        email_data={
                            "count": len(processed_emails),
                            "total": len(raw_emails_stored)
                        }
                    )
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                # CRITICAL: Even if processed_email creation fails, create minimal version
                logger.error(f"CRITICAL: Failed to create processed_email for {msg_id[:20]}: {e}", exc_info=True)
                try:
                    minimal_email = {
                        "email_id": msg_id,
                        "thread_id": "",
                        "internal_date": 0,
                        "company_name": "UNKNOWN",
                        "role": "",
                        "application_status": "OTHER_JOB_RELATED",
                        "confidence_score": 0.0,
                        "received_at": datetime.utcnow().isoformat(),
                        "summary": f"Error: {str(e)[:100]}",
                        "from_email": from_email,
                        "to_email": "",
                        "body_text": None,
                        "subject": subject or "Error"
                    }
                    processed_emails.append(minimal_email)
                    status_counts['OTHER_JOB_RELATED'] += 1
                    logger.info(f"[RECOVERED] Added minimal email for {msg_id[:20]}")
                except Exception as final_error:
                    logger.error(f"FATAL: Could not even create minimal email: {final_error}", exc_info=True)
        
        logger.info(f"[STEP 2] ✅ Classification complete: {len(processed_emails)} emails processed from {len(raw_emails_stored)} raw emails")
        logger.info(f"📊 [DATA FLOW] Classified: {len(processed_emails)} emails")
        logger.info(f"📊 [DATA FLOW] NO LIMIT on classification - ALL emails classified")
        
        # RULE 11: COMPREHENSIVE LOGGING (MANDATORY) - ZERO FALSE NEGATIVES
        total_fetched = len(emails)
        total_raw_stored = len(raw_emails_stored)  # STEP 1: All raw emails stored
        total_classified = len(processed_emails)  # STEP 2: All emails classified
        total_non_job = status_counts.get('NON_JOB', 0)
        total_job_related = total_classified - total_non_job
        
        logger.info(f"[STEP 1] ✅ Raw emails stored: {total_raw_stored}")
        logger.info(f"[STEP 2] ✅ Emails classified: {total_classified}")
        
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("[SYNC STATS] RULE 11 - COMPREHENSIVE SUMMARY")
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"Total fetched: {total_fetched}")
        logger.info(f"Total raw stored: {total_raw_stored} (STEP 1: ALL emails stored)")
        logger.info(f"Total classified: {total_classified} (STEP 2: ALL emails classified)")
        logger.info(f"Pages fetched: {pages_fetched}")
        logger.info(f"")
        logger.info(f"Status breakdown:")
        logger.info(f"  Applied: {status_counts.get('APPLIED', 0)}")
        logger.info(f"  Application Received: {status_counts.get('APPLICATION_RECEIVED', 0)}")
        logger.info(f"  Rejected: {status_counts.get('REJECTED', 0)}")
        logger.info(f"  Interview: {status_counts.get('INTERVIEW', 0)}")
        logger.info(f"  Assessment: {status_counts.get('ASSESSMENT', 0)}")
        logger.info(f"  Screening: {status_counts.get('SCREENING', 0)}")
        logger.info(f"  Offer: {status_counts.get('OFFER', 0)}")
        logger.info(f"  Accepted: {status_counts.get('ACCEPTED', 0)}")
        logger.info(f"  Withdrawn: {status_counts.get('WITHDRAWN', 0)}")
        logger.info(f"  Follow-up: {status_counts.get('FOLLOW_UP', 0)}")
        logger.info(f"  Other Job Related: {status_counts.get('OTHER_JOB_RELATED', 0)} (DEFAULT)")
        logger.info(f"  Non-Job: {status_counts.get('NON_JOB', 0)}")
        logger.info(f"")
        logger.info(f"Job-related: {total_job_related}")
        logger.info(f"Non-job: {total_non_job}")
        logger.info("═══════════════════════════════════════════════════════════")
        
        # REQUIREMENT 8: Error detection - log ERROR if numbers don't match
        total_status_sum = sum(status_counts.values())
        if total_fetched != total_raw_stored:
            logger.error(f"❌ ERROR: Total fetched ({total_fetched}) != total raw stored ({total_raw_stored})")
        if total_raw_stored != total_classified:
            logger.error(f"❌ ERROR: Total raw stored ({total_raw_stored}) != total classified ({total_classified})")
        if total_classified != total_status_sum:
            logger.error(f"❌ ERROR: Total classified ({total_classified}) != sum of status counts ({total_status_sum})")
        
        # Update progress
        yield send_sse_message(
            f"Classified {total_classified} emails (all {total_raw_stored} raw emails processed)",
            progress=70,
            stage="Classifying emails"
        )
        await asyncio.sleep(0.1)
        
        # CRITICAL ERROR CHECK: If 0 emails classified, this is a BUG
        if not processed_emails:
            logger.error(f"❌ CRITICAL ERROR: 0 emails classified out of {total_raw_stored} raw emails stored!")
            logger.error(f"❌ Raw emails were stored, but classification failed for ALL emails")
            logger.error(f"❌ Check classification logic - it's rejecting ALL emails")
            
            # Log first 10 raw email subjects for debugging
            logger.error(f"[DEBUG] First 10 raw email subjects:")
            for i, raw_email in enumerate(raw_emails_stored[:10], 1):
                logger.error(f"  {i}. {raw_email.get('subject', 'No Subject')[:80]}")
            
            yield send_sse_message(
                f"ERROR: 0 emails classified (check logs) - classification logic may be broken",
                progress=95,
                stage="Error"
            )
            # Still update sync time
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
            
            yield send_sse_message("Sync completed with errors", progress=100, stage="Complete")
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
                        "thread_id": email.get("thread_id", ""),
                        "company_name": email["company_name"],
                        "role": email["role"],
                        "application_status": email["application_status"],
                        "confidence_score": email["confidence_score"],
                        "received_at": received_at_dt.isoformat(),
                        "summary": email.get("summary"),
                        # RULE 8: Additional fields for email storage
                        "from_email": email.get("from_email"),
                        "to_email": email.get("to_email"),
                        "body_text": email.get("body_text"),
                        "internal_date": email.get("internal_date"),
                        "subject": email.get("subject")
                    })
                
                # Send to application-service ingest endpoint
                ingest_url = f"{settings.APPLICATION_SERVICE_URL}/ingest/from-email-ai"
                logger.info(f"Sending {len(ingest_data)} emails to {ingest_url} for user {user_id}")
                logger.info(f"📊 [DATA FLOW] Sending to application-service: {len(ingest_data)} emails")
                logger.info(f"📊 [DATA FLOW] NO LIMIT on ingest - ALL emails being sent")
                response = await client.post(
                    ingest_url,
                    json=ingest_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-User-ID": str(user_id)  # CRITICAL: Pass user_id so applications are associated with user
                    },
                    timeout=60.0  # Increased timeout for batch processing
                )
                logger.info(f"Application-service response: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    applications_created = result.get("accepted", len(ingest_data))
                    yield send_sse_message(
                        f"✅ Successfully stored {applications_created} applications in database",
                        progress=90,
                        stage="Updating Database"
                    )
                    logger.info(f"✅ Ingested {applications_created} applications for user {user_id} (sent {len(ingest_data)} emails)")
                elif response.status_code == 404:
                    logger.error(f"❌ Ingest endpoint not found: {ingest_url}")
                    yield send_sse_message(
                        f"Error: Application service ingest endpoint not found. Check service is running.",
                        progress=85,
                        stage="Error"
                    )
                else:
                    error_text = response.text[:200] if hasattr(response, 'text') else str(response.status_code)
                    logger.error(f"❌ Failed to ingest: {response.status_code} - {error_text}")
                    yield send_sse_message(
                        f"Warning: Failed to ingest some emails (Status: {response.status_code})",
                        progress=85,
                        stage="Updating Database"
                    )
        except Exception as e:
            yield send_sse_message(
                f"Error ingesting emails: {str(e)}",
                progress=85,
                stage="Error"
            )
            logger.error(f"Error ingesting emails to application-service: {e}", exc_info=True)
        
        # Step 5: Update last_synced_at and last_message_internal_date (INCREMENTAL SYNC)
        yield send_sse_message("Updating sync timestamp...", progress=95, stage="Finalizing")
        
        # Get the most recent email's internal date for incremental sync
        # Check ALL emails (including rejected) to get the absolute most recent
        most_recent_internal_date = None
        if emails:
            all_internal_dates = [e.get('internal_date', 0) for e in emails if e.get('internal_date')]
            if all_internal_dates:
                most_recent_internal_date = max(all_internal_dates)
                logger.info(f"[INCREMENTAL SYNC] Most recent email internal_date: {most_recent_internal_date}")
        
        try:
            async with httpx.AsyncClient() as client:
                sync_update_data = {
                    "last_synced_at": datetime.utcnow().isoformat()
                }
                if most_recent_internal_date:
                    # Convert internal_date (milliseconds) to ISO format
                    from datetime import datetime as dt
                    sync_update_data["last_message_internal_date"] = dt.fromtimestamp(most_recent_internal_date / 1000).isoformat()
                    logger.info(f"[INCREMENTAL SYNC] Most recent email internal_date: {most_recent_internal_date} ({sync_update_data['last_message_internal_date']})")
                
                response = await client.post(
                    f"{settings.AUTH_SERVICE_URL}/api/gmail/update-sync-time",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=sync_update_data,
                    timeout=5.0
                )
                if response.status_code == 200:
                    logger.info(f"[INCREMENTAL SYNC] ✅ Updated last_synced_at and last_message_internal_date")
                else:
                    logger.warning(f"[INCREMENTAL SYNC] Update returned {response.status_code}, but continuing")
        except Exception as e:
            logger.warning(f"Failed to update sync time: {e}")
        
        # Create summary with status breakdown
        status_counts = {}
        for email in processed_emails:
            status = email.get("application_status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        status_summary = ", ".join([f"{count} {status}" for status, count in sorted(status_counts.items())])
        
        # FINAL COMPREHENSIVE LOG
        logger.info("=" * 80)
        logger.info("[SYNC COMPLETE] FINAL SUMMARY")
        logger.info(f"Total emails scanned: {total_scanned}")
        logger.info(f"Total job emails stored: {len(processed_emails)}")
        logger.info(f"Status breakdown: {status_summary}")
        logger.info(f"Applications created/updated: {applications_created}")
        logger.info(f"Most recent email internal date: {most_recent_internal_date}")
        logger.info("=" * 80)
        
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

    async def locked_generator():
        acquired = False
        async with _ACTIVE_GMAIL_SYNCS_LOCK:
            if user_id in _ACTIVE_GMAIL_SYNCS:
                logger.info(f"Sync skipped (already running) user_id={user_id}")
                yield send_sse_message(
                    "Sync skipped: sync already running",
                    progress=100,
                    stage="Skipped"
                )
                return
            _ACTIVE_GMAIL_SYNCS.add(user_id)
            acquired = True

        try:
            generator = sync_gmail_emails_streaming(user_id, access_token)
            logger.info(f"Generator created for user {user_id}")
            async for msg in generator:
                yield msg
        finally:
            if acquired:
                async with _ACTIVE_GMAIL_SYNCS_LOCK:
                    _ACTIVE_GMAIL_SYNCS.discard(user_id)

    return StreamingResponse(
        locked_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )
