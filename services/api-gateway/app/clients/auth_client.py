from httpx import AsyncClient, Response
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()


class AuthClient:
    """Client for communicating with auth-service."""
    
    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL
        self.timeout = settings.HTTP_TIMEOUT
    
    async def forward_request(
        self,
        method: str,
        path: str,
        headers: dict = None,
        data: dict = None,
        files: dict = None
    ) -> Response:
        """Forward a request to auth-service."""
        url = f"{self.base_url}{path}"
        client_headers = headers.copy() if headers else {}
        
        async with AsyncClient(timeout=self.timeout) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=client_headers)
                elif method.upper() == "POST":
                    if files:
                        response = await client.post(url, headers=client_headers, data=data, files=files)
                    else:
                        response = await client.post(url, headers=client_headers, json=data)
                else:
                    response = await client.request(method, url, headers=client_headers, json=data)
                
                return response
            except Exception as e:
                logger.error(f"Error forwarding request to auth-service: {e}")
                raise


auth_client = AuthClient()
