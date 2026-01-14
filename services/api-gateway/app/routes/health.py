from fastapi import APIRouter
from httpx import AsyncClient
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint that verifies service connectivity."""
    import asyncio
    
    health_status = {
        "status": "ok",
        "gateway": "healthy",
        "services": {}
    }
    
    # Check services in parallel with shorter timeouts for faster response
    async def check_application_service():
        try:
            async with AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{settings.APPLICATION_SERVICE_URL}/health")
                return {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code
                }
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                return {"status": "timeout", "status_code": None}
            logger.warning(f"Application service health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)[:100]}  # Truncate error message
    
    async def check_auth_service():
        try:
            async with AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{settings.AUTH_SERVICE_URL}/health")
                return {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code
                }
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                return {"status": "timeout", "status_code": None}
            logger.warning(f"Auth service health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)[:100]}  # Truncate error message
    
    # Check both services in parallel (faster than sequential)
    # Add overall timeout to ensure health check doesn't hang
    try:
        app_result, auth_result = await asyncio.wait_for(
            asyncio.gather(
                check_application_service(),
                check_auth_service(),
                return_exceptions=True
            ),
            timeout=5.0  # Overall timeout of 5 seconds
        )
        
        # Handle application-service result
        if isinstance(app_result, Exception):
            health_status["services"]["application-service"] = {"status": "error", "error": str(app_result)[:100]}
            health_status["status"] = "degraded"
        else:
            health_status["services"]["application-service"] = app_result
            if app_result.get("status") != "healthy":
                health_status["status"] = "degraded"
        
        # Handle auth-service result
        if isinstance(auth_result, Exception):
            health_status["services"]["auth-service"] = {"status": "error", "error": str(auth_result)[:100]}
            health_status["status"] = "degraded"
        else:
            health_status["services"]["auth-service"] = auth_result
            if auth_result.get("status") != "healthy":
                health_status["status"] = "degraded"
    except asyncio.TimeoutError:
        logger.warning("Health check timed out after 5 seconds")
        health_status["status"] = "degraded"
        health_status["services"]["application-service"] = {"status": "timeout"}
        health_status["services"]["auth-service"] = {"status": "timeout"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["status"] = "error"
        health_status["error"] = str(e)[:100]
    
    return health_status
