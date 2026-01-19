"""
Integration test for Gmail sync flow
Tests: Start sync → receive sync_id → poll progress endpoint → returns valid JSON
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db, init_db, engine
from sqlalchemy.orm import Session

@pytest.mark.asyncio
async def test_sync_flow_contract():
    """
    Test that sync flow follows the correct contract:
    1. POST /gmail/sync returns { sync_id, status, ... }
    2. GET /gmail/sync/progress/{sync_id} returns valid JSON
    3. sync_id is never undefined/null/empty
    """
    # Use httpx.AsyncClient for async apps (recommended)
    # Rule: Async apps → httpx.AsyncClient only
    # AsyncClient uses ASGITransport to connect to FastAPI app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initialize database
        init_db()
        
        # Mock user data
        user_email = "test@example.com"
        user_id = "test@example.com"  # JWT sub is email
        
        # Step 1: Start sync
        # Endpoint is /sync/start, not /gmail/sync
        response = await client.post(
            "/sync/start",
            json={"user_id": user_id, "user_email": user_email}
        )
        
        # Should return 202 (Accepted) or 409 (if already running)
        assert response.status_code in [202, 409], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 202:
            data = response.json()
            
            # CONTRACT: Must return sync_id
            assert "sync_id" in data, "Response must include sync_id"
            sync_id = data["sync_id"]
            
            # CONTRACT: sync_id must be valid (not undefined/null/empty)
            assert sync_id, f"sync_id must not be empty, got: '{sync_id}'"
            assert sync_id != "undefined", f"sync_id must not be 'undefined', got: '{sync_id}'"
            assert sync_id != "null", f"sync_id must not be 'null', got: '{sync_id}'"
            
            # CONTRACT: Must return status
            assert "status" in data, "Response must include status"
            assert data["status"] in ["queued", "pending", "running", "completed", "failed"], f"Invalid status: {data['status']}"
            
            # Step 2: Poll progress with valid sync_id
            # Endpoint is /sync/status, not /gmail/sync/progress
            progress_response = await client.get(
                "/sync/status",
                params={"sync_id": sync_id, "user_id": user_id}
            )
            
            # Endpoint always returns 200 (never 404)
            assert progress_response.status_code == 200, \
                f"Progress endpoint should return 200, got: {progress_response.status_code}"
            
            progress_data = progress_response.json()
            assert "status" in progress_data, "Progress response must include status"
            assert "total_emails" in progress_data or "emails_fetched" in progress_data, "Progress response must include email counts"
        
        # Step 3: Test that undefined sync_id is handled (returns 200 with not_found status)
        invalid_response = await client.get(
            "/sync/status",
            params={"sync_id": "undefined", "user_id": user_id}
        )
        # Endpoint returns 200 with status="not_found" (not 400)
        assert invalid_response.status_code == 200, \
            f"Should return 200 for invalid sync_id, got: {invalid_response.status_code}"
        invalid_data = invalid_response.json()
        assert invalid_data.get("status") == "not_found", \
            f"Should return status='not_found' for invalid sync_id, got: {invalid_data.get('status')}"
        
        # Step 4: Test that null sync_id is handled (returns 200 with not_found status)
        null_response = await client.get(
            "/sync/status",
            params={"sync_id": "null", "user_id": user_id}
        )
        # Endpoint returns 200 with status="not_found" (not 400)
        assert null_response.status_code == 200, \
            f"Should return 200 for null sync_id, got: {null_response.status_code}"
        null_data = null_response.json()
        assert null_data.get("status") == "not_found", \
            f"Should return status='not_found' for null sync_id, got: {null_data.get('status')}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
