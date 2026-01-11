from httpx import AsyncClient, Response
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()


class ApplicationClient:
    """Client for communicating with application-service."""
    
    def __init__(self):
        self.base_url = settings.APPLICATION_SERVICE_URL
        self.timeout = settings.HTTP_TIMEOUT
    
    async def forward_request(
        self,
        method: str,
        path: str,
        headers: dict = None,
        params: dict = None,
        data: dict = None,
        files: dict = None,
        content: bytes = None
    ) -> Response:
        """Forward a request to application-service."""
        url = f"{self.base_url}{path}"
        client_headers = headers.copy() if headers else {}
        # Remove content-type for multipart/form-data (httpx sets it automatically)
        if files:
            client_headers.pop("content-type", None)
        
        async with AsyncClient(timeout=self.timeout) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=client_headers, params=params)
                elif method.upper() == "POST":
                    if files:
                        # Handle multipart file upload
                        file_items = {}
                        for key, file_tuple in files.items():
                            if isinstance(file_tuple, tuple) and len(file_tuple) == 3:
                                file_items[key] = (file_tuple[0], file_tuple[1], file_tuple[2])
                            else:
                                file_items[key] = file_tuple
                        response = await client.post(url, headers=client_headers, data=data, files=file_items)
                    elif content:
                        response = await client.post(url, headers=client_headers, content=content)
                    else:
                        response = await client.post(url, headers=client_headers, json=data)
                elif method.upper() == "PATCH":
                    response = await client.patch(url, headers=client_headers, json=data)
                else:
                    response = await client.request(method, url, headers=client_headers, json=data, params=params)
                
                return response
            except Exception as e:
                logger.error(f"Error forwarding request to application-service: {e}")
                raise


application_client = ApplicationClient()
