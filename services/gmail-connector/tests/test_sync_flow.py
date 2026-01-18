"""
Integration test for Gmail sync flow
Tests: Start sync → receive sync_id → poll progress endpoint → returns valid JSON
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, init_db, engine
from sqlalchemy.orm import Session

client = TestClient(app)

def test_sync_flow_contract():
    """
    Test that sync flow follows the correct contract:
    1. POST /gmail/sync returns { sync_id, status, ... }
    2. GET /gmail/sync/progress/{sync_id} returns valid JSON
    3. sync_id is never undefined/null/empty
    """
    # Initialize database
    init_db()
    
    # Mock user data
    user_email = "test@example.com"
    user_id = "test@example.com"  # JWT sub is email
    
    # Step 1: Start sync
    response = client.post(
        "/gmail/sync",
        json={"user_id": user_id, "user_email": user_email}
    )
    
    # Should return 200 or 409 (if already running)
    assert response.status_code in [200, 409], f"Unexpected status: {response.status_code}"
    
    if response.status_code == 200:
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
        assert data["status"] in ["running", "completed", "failed"], f"Invalid status: {data['status']}"
        
        # Step 2: Poll progress with valid sync_id
        progress_response = client.get(
            f"/gmail/sync/progress/{sync_id}",
            params={"user_id": user_id}
        )
        
        # Should return 200 or 404 (if job not found yet)
        assert progress_response.status_code in [200, 404], \
            f"Progress endpoint returned unexpected status: {progress_response.status_code}"
        
        if progress_response.status_code == 200:
            progress_data = progress_response.json()
            assert "status" in progress_data, "Progress response must include status"
            assert "total_emails" in progress_data, "Progress response must include total_emails"
            assert "fetched_emails" in progress_data, "Progress response must include fetched_emails"
            assert "classified" in progress_data, "Progress response must include classified"
    
    # Step 3: Test that undefined sync_id is rejected
    invalid_response = client.get(
        "/gmail/sync/progress/undefined",
        params={"user_id": user_id}
    )
    assert invalid_response.status_code == 400, \
        f"Should reject 'undefined' sync_id with 400, got: {invalid_response.status_code}"
    
    # Step 4: Test that null sync_id is rejected
    null_response = client.get(
        "/gmail/sync/progress/null",
        params={"user_id": user_id}
    )
    assert null_response.status_code == 400, \
        f"Should reject 'null' sync_id with 400, got: {null_response.status_code}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
