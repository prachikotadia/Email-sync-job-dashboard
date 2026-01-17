import os
import secrets
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import httpx

class GoogleOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
        self.scopes = [
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/gmail.readonly",
        ]
        
        self.client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }

    def get_authorization_url(self):
        """
        Generate OAuth authorization URL
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        flow.state = state
        
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes=True,
            prompt="consent"
        )
        
        return authorization_url

    async def exchange_code(self, code: str):
        """
        Exchange authorization code for access token
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

    async def get_user_info(self, access_token: str):
        """
        Get user info from Google API
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()
