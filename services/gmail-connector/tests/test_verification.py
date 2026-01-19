"""
Verification Tests - Acceptance Criteria (MANDATORY)

Tests hard acceptance criteria to prevent "looks like it works" bugs.
"""
import pytest
from unittest.mock import Mock, patch
from app.verification import verify_sync_completion, verify_idempotency, verify_dashboard_counts_match
from app.database import SyncJob, Application, SyncStateEnum, SyncJobStatus


class TestVerificationAcceptanceCriteria:
    """Test acceptance criteria verification"""
    
    def test_gmail_total_equals_fetched_count(self):
        """Test ACCEPTANCE CRITERIA 1: Gmail total count == fetched count"""
        # Create mock sync job
        sync_job = Mock(spec=SyncJob)
        sync_job.id = "test_job_id"
        sync_job.total_emails = 10000
        sync_job.counts_fetched = 10000
        sync_job.counts_classified = 5000
        sync_job.checkpoint = {
            "mode": "full_history",
            "page_token": None,
            "sync_state": SyncStateEnum.COMPLETED.value
        }
        
        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5000
        mock_db.query.return_value.filter.return_value.distinct.return_value.count.return_value = 5000
        
        # Should pass - counts match
        result = verify_sync_completion(mock_db, sync_job, user_id=1)
        assert result["passed"] is True
    
    def test_gmail_total_not_equals_fetched_count_fails(self):
        """Test verification fails when Gmail total != fetched count"""
        sync_job = Mock(spec=SyncJob)
        sync_job.id = "test_job_id"
        sync_job.total_emails = 10000
        sync_job.counts_fetched = 9500  # Missing 500 emails - BUG!
        sync_job.counts_classified = 5000
        sync_job.checkpoint = {"mode": "full_history", "page_token": None, "sync_state": "COMPLETED"}
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5000
        mock_db.query.return_value.filter.return_value.distinct.return_value.count.return_value = 5000
        
        # Should fail - counts don't match
        result = verify_sync_completion(mock_db, sync_job, user_id=1)
        assert result["passed"] is False
        assert len(result["errors"]) > 0
        assert "Gmail total" in result["errors"][0]
    
    def test_db_stored_equals_classified_count(self):
        """Test ACCEPTANCE CRITERIA 2: DB stored count == classified count"""
        sync_job = Mock(spec=SyncJob)
        sync_job.id = "test_job_id"
        sync_job.total_emails = 10000
        sync_job.counts_fetched = 10000
        sync_job.counts_classified = 5000
        sync_job.checkpoint = {"mode": "full_history", "page_token": None, "sync_state": "COMPLETED"}
        
        # Mock DB count matches classified count
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5000
        mock_db.query.return_value.filter.return_value.distinct.return_value.count.return_value = 5000
        
        result = verify_sync_completion(mock_db, sync_job, user_id=1)
        assert result["passed"] is True
    
    def test_db_stored_not_equals_classified_count_fails(self):
        """Test verification fails when DB stored != classified count"""
        sync_job = Mock(spec=SyncJob)
        sync_job.id = "test_job_id"
        sync_job.total_emails = 10000
        sync_job.counts_fetched = 10000
        sync_job.counts_classified = 5000
        sync_job.checkpoint = {"mode": "full_history", "page_token": None, "sync_state": "COMPLETED"}
        
        # Mock DB count is different - BUG!
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 4800  # Missing 200!
        mock_db.query.return_value.filter.return_value.distinct.return_value.count.return_value = 4800
        
        result = verify_sync_completion(mock_db, sync_job, user_id=1)
        assert result["passed"] is False
        assert any("DB stored" in err for err in result["errors"])
    
    def test_no_duplicate_message_ids(self):
        """Test verification passes when no duplicate message IDs"""
        sync_job = Mock(spec=SyncJob)
        sync_job.id = "test_job_id"
        sync_job.total_emails = 10000
        sync_job.counts_fetched = 10000
        sync_job.counts_classified = 5000
        sync_job.checkpoint = {"mode": "full_history", "page_token": None, "sync_state": "COMPLETED"}
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5000
        # Unique count equals total count - no duplicates
        mock_db.query.return_value.filter.return_value.distinct.return_value.count.return_value = 5000
        
        result = verify_sync_completion(mock_db, sync_job, user_id=1)
        assert result["passed"] is True
    
    def test_duplicate_message_ids_fails(self):
        """Test verification fails when duplicate message IDs found"""
        sync_job = Mock(spec=SyncJob)
        sync_job.id = "test_job_id"
        sync_job.total_emails = 10000
        sync_job.counts_fetched = 10000
        sync_job.counts_classified = 5000
        sync_job.checkpoint = {"mode": "full_history", "page_token": None, "sync_state": "COMPLETED"}
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5000
        # Unique count is less than total - duplicates exist!
        mock_db.query.return_value.filter.return_value.distinct.return_value.count.return_value = 4950  # 50 duplicates
        
        result = verify_sync_completion(mock_db, sync_job, user_id=1)
        assert result["passed"] is False
        assert any("duplicate" in err.lower() for err in result["errors"])


class TestIdempotencyVerification:
    """Test ACCEPTANCE CRITERIA 4: Re-sync without new emails changes NOTHING"""
    
    def test_idempotency_passes_when_counts_match(self):
        """Test idempotency verification passes when counts unchanged"""
        before_count = 5000
        after_count = 5000
        
        mock_db = Mock()
        result = verify_idempotency(mock_db, user_id=1, before_count=before_count, after_count=after_count)
        
        assert result["passed"] is True
        assert len(result["errors"]) == 0
    
    def test_idempotency_fails_when_counts_change(self):
        """Test idempotency verification fails when counts change"""
        before_count = 5000
        after_count = 5100  # Increased - duplicates or data issue!
        
        mock_db = Mock()
        result = verify_idempotency(mock_db, user_id=1, before_count=before_count, after_count=after_count)
        
        assert result["passed"] is False
        assert len(result["errors"]) > 0
        assert "changed count" in result["errors"][0].lower()
    
    def test_idempotency_fails_on_data_loss(self):
        """Test idempotency verification fails on data loss"""
        before_count = 5000
        after_count = 4900  # Decreased - data loss!
        
        mock_db = Mock()
        result = verify_idempotency(mock_db, user_id=1, before_count=before_count, after_count=after_count)
        
        assert result["passed"] is False
        assert len(result["errors"]) > 0


class TestDashboardCountsVerification:
    """Test ACCEPTANCE CRITERIA 3: Dashboard count == DB count"""
    
    def test_dashboard_counts_match_passes(self):
        """Test verification passes when API count matches DB count"""
        api_response = {
            "total": 5000,
            "applications": [{"id": i} for i in range(5000)]
        }
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 5000
        
        result = verify_dashboard_counts_match(mock_db, user_id=1, api_response=api_response)
        
        assert result["passed"] is True
        assert len(result["errors"]) == 0
    
    def test_dashboard_counts_mismatch_fails(self):
        """Test verification fails when API count != DB count"""
        api_response = {
            "total": 5000,
            "applications": [{"id": i} for i in range(5000)]
        }
        
        mock_db = Mock()
        # DB has different count - BUG!
        mock_db.query.return_value.filter.return_value.count.return_value = 5100
        
        result = verify_dashboard_counts_match(mock_db, user_id=1, api_response=api_response)
        
        assert result["passed"] is False
        assert len(result["errors"]) > 0
        assert "API total" in result["errors"][0]
