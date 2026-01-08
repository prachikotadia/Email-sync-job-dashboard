import httpx
from fastapi import Request, HTTPException, Response
from starlette.background import BackgroundTask
from typing import Optional

async def reverse_proxy(request: Request, service_url: str, path: str):
    """
    Reverse proxy logic to forward requests to microservices.
    """
    client = httpx.AsyncClient(base_url=service_url, timeout=30.0)
    
    url = httpx.URL(path=path, query=request.url.query.encode("utf-8"))
    
    # Forward headers but exclude host to avoid confusion
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None) # Let httpx handle this
    
    try:
        req = client.build_request(
            request.method,
            url,
            headers=headers,
            content=request.stream()
        )
        r = await client.send(req, stream=True)
        
        return Response(
            content=r.aiter_bytes(),
            status_code=r.status_code,
            headers=dict(r.headers),
            background=BackgroundTask(r.aclose)
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Service Unavailable: Could not connect to backend.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gateway Error: {str(e)}")
    finally:
        # Client closes in background task usually, but good to be explicit if not streaming
        pass 
