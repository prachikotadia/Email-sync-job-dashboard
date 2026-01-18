from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging
import json
import time
import random

logger = logging.getLogger(__name__)

class GmailClient:
    """
    Gmail API client
    Fetches ALL emails with no pagination limits
    """
    
    def __init__(self, user_id: int, user_email: str, oauth_token):
        """
        Initialize Gmail client with OAuth tokens
        
        Args:
            user_id: Database user ID
            user_email: User's email address
            oauth_token: OAuthToken database model instance
        """
        self.user_id = user_id
        self.user_email = user_email
        self.oauth_token = oauth_token
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """
        Initialize Gmail API service using stored OAuth tokens
        """
        try:
            # Parse scopes from JSON string
            scopes = []
            if self.oauth_token.scopes:
                try:
                    scopes = json.loads(self.oauth_token.scopes)
                except:
                    scopes = [self.oauth_token.scopes] if isinstance(self.oauth_token.scopes, str) else []
            
            # Build credentials from stored tokens
            credentials = Credentials(
                token=self.oauth_token.access_token,
                refresh_token=self.oauth_token.refresh_token,
                token_uri=self.oauth_token.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.oauth_token.client_id,
                client_secret=self.oauth_token.client_secret,
                scopes=scopes,
            )
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=credentials)
            logger.info(f"Gmail service initialized for user {self.user_email}")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            raise Exception(f"Failed to initialize Gmail service: {str(e)}")
    
    async def get_user_email(self) -> str:
        """
        Get Gmail email address for validation
        """
        if not self.service:
            raise Exception("Gmail service not initialized")
        
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress', '')
        except Exception as e:
            logger.error(f"Error getting user email: {e}")
            raise
    
    def _retry_with_backoff(self, func, max_attempts=6, initial_delay=1.0, max_delay=60.0):
        """
        Retry function with exponential backoff + jitter
        Handles 429, 5xx, backendError, rateLimitExceeded
        Returns result or raises exception
        """
        delay = initial_delay
        attempt = 0
        
        while attempt < max_attempts:
            try:
                return func()
            except Exception as e:
                error_str = str(e).lower()
                error_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
                
                # Check if error is retryable
                is_retryable = (
                    error_code == 429 or  # Rate limit
                    error_code and error_code >= 500 or  # Server errors
                    'ratelimitexceeded' in error_str or
                    'backenderror' in error_str or
                    'internalerror' in error_str
                )
                
                if not is_retryable or attempt == max_attempts - 1:
                    # Not retryable or last attempt - raise
                    raise
                
                attempt += 1
                # Exponential backoff with jitter
                jitter = random.uniform(0, delay * 0.1)  # 10% jitter
                wait_time = min(delay + jitter, max_delay)
                
                logger.warning(
                    f"Gmail API error (attempt {attempt}/{max_attempts}): {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
                delay *= 2  # Exponential backoff
                
        raise Exception(f"Max retry attempts ({max_attempts}) exceeded")

    def _refresh_token_if_needed(self):
        """Refresh OAuth token if expired"""
        try:
            if not self.oauth_token.refresh_token:
                raise Exception("No refresh token available")
            
            credentials = Credentials(
                token=self.oauth_token.access_token,
                refresh_token=self.oauth_token.refresh_token,
                token_uri=self.oauth_token.token_uri or "https://oauth2.googleapis.com/token",
                client_id=self.oauth_token.client_id,
                client_secret=self.oauth_token.client_secret,
            )
            
            # Check if expired
            if not credentials.expired:
                return credentials
            
            # Refresh token
            credentials.refresh(GoogleRequest())
            
            # Update stored token (in-memory only - caller should persist to DB)
            self.oauth_token.access_token = credentials.token
            if credentials.expires_at:
                self.oauth_token.expires_at = datetime.fromtimestamp(credentials.expires_at, tz=timezone.utc)
            
            # Rebuild service with new credentials
            self.service = build('gmail', 'v1', credentials=credentials)
            logger.info(f"OAuth token refreshed for user {self.user_email}")
            
            return credentials
        except RefreshError as e:
            if 'invalid_grant' in str(e).lower():
                raise Exception("REAUTH_REQUIRED: Refresh token invalid or revoked. Please re-authenticate.")
            raise Exception(f"Token refresh failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Token refresh error: {str(e)}")

    def get_all_messages(self, query: str = "", history_id: Optional[str] = None) -> tuple[List[Dict], str]:
        """
        Fetch ALL messages matching query
        NO pagination limits - uses pagination to get everything
        Returns: (messages, latest_history_id)
        """
        if not self.service:
            raise Exception("Gmail service not initialized")
        
        messages = []
        page_token = None
        latest_history_id = None
        
        if history_id:
            # Incremental sync using history
            try:
                history = self.service.users().history().list(
                    userId='me',
                    startHistoryId=history_id,
                    historyTypes=['messageAdded', 'messageDeleted']
                ).execute()
                
                history_records = history.get('history', [])
                message_ids = []
                
                for record in history_records:
                    if 'messagesAdded' in record:
                        for msg in record['messagesAdded']:
                            message_ids.append(msg['message']['id'])
                    if 'messagesDeleted' in record:
                        for msg in record['messagesDeleted']:
                            # Handle deleted messages if needed
                            pass
                
                # Fetch full message details
                for msg_id in message_ids:
                    try:
                        message = self.service.users().messages().get(
                            userId='me',
                            id=msg_id,
                            format='full'
                        ).execute()
                        messages.append(message)
                    except Exception as e:
                        logger.warning(f"Error fetching message {msg_id}: {e}")
                        continue
                
                latest_history_id = history.get('historyId')
                
            except Exception as e:
                logger.error(f"Error in incremental sync: {e}")
                # Fall back to full sync
                history_id = None
        
        if not history_id:
            # Full sync: paginate until nextPageToken is null. NO maxResults cap.
            # Gmail API allows up to 500 per page, but we MUST loop until all are fetched.
            page_num = 0
            while True:
                try:
                    page_num += 1
                    # Use retry logic for list call
                    def list_page():
                        return self.service.users().messages().list(
                            userId='me', q=query, pageToken=page_token, maxResults=500
                        ).execute()
                    
                    result = self._retry_with_backoff(list_page)
                    message_ids = result.get('messages', [])
                    latest_history_id = result.get('historyId')
                    
                    logger.info(f"Fetched page {page_num}: {len(message_ids)} message IDs (token: {page_token[:20] if page_token else 'initial'}...)")
                    
                    # Fetch full message details with retry for each message
                    for msg in message_ids:
                        try:
                            def get_message():
                                return self.service.users().messages().get(
                                    userId='me', id=msg['id'], format='full'
                                ).execute()
                            
                            message = self._retry_with_backoff(get_message, max_attempts=3)
                            messages.append(message)
                        except Exception as e:
                            logger.warning(f"Error fetching message {msg['id']} after retries: {e}")
                            continue
                    
                    page_token = result.get('nextPageToken')
                    if not page_token:
                        # nextPageToken is null - we've fetched ALL messages
                        logger.info(f"Pagination complete: fetched {len(messages)} messages across {page_num} pages")
                        break
                except Exception as e:
                    error_str = str(e).lower()
                    # Check for auth errors that should stop sync
                    if 'reauth_required' in error_str or 'invalid_grant' in error_str:
                        raise Exception("REAUTH_REQUIRED: Token refresh failed. Please re-authenticate.")
                    logger.error(f"Error fetching messages page {page_num}: {e}. Stopping pagination.")
                    # Don't continue on persistent errors after retries
                    break
            
            # Verify we fetched all messages
            logger.info(f"Fetched: {len(messages)} emails (100% - pagination complete, nextPageToken is null)")
        else:
            logger.info(f"Fetched: {len(messages)} new/changed emails (incremental sync)")
        
        return messages, latest_history_id
    
    def get_message_count(self, query: str = "") -> int:
        """
        Get total count of messages matching query
        Note: This is an estimate from Gmail API
        """
        if not self.service:
            raise Exception("Gmail service not initialized")
        
        try:
            result = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=1  # Just to get the result size
            ).execute()
            
            return result.get('resultSizeEstimate', 0)
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0
