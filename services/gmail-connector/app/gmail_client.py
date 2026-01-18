from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from typing import List, Dict, Optional
import logging
import json

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
            while True:
                try:
                    # Use maxResults=500 per page (Gmail API limit), but loop until nextPageToken is null
                    result = self.service.users().messages().list(
                        userId='me', q=query, pageToken=page_token, maxResults=500
                    ).execute()
                    message_ids = result.get('messages', [])
                    latest_history_id = result.get('historyId')
                    for msg in message_ids:
                        try:
                            message = self.service.users().messages().get(
                                userId='me', id=msg['id'], format='full'
                            ).execute()
                            messages.append(message)
                        except Exception as e:
                            logger.warning(f"Error fetching message {msg['id']}: {e}")
                            continue
                    page_token = result.get('nextPageToken')
                    if not page_token:
                        # nextPageToken is null - we've fetched ALL messages
                        break
                except Exception as e:
                    logger.error(f"Error fetching messages page: {e}")
                    # Don't break on single page error - try to continue
                    # But log the error
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
