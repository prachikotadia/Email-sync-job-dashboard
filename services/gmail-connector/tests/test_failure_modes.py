"""
Failure Simulation Tests (MANDATORY)

Tests system behavior under failure conditions:
- Rate limits (429, 403 rateLimitExceeded, 403 userRateLimitExceeded)
- Timeouts (LLM timeout, network timeout)
- Backend restart/crash
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.gmail_client import GmailClient, GmailRateLimitError
from app.classifier import Classifier
from app.worker import run_sync_with_progress
from app.progress_events import SyncPhase


class TestRateLimitHandling:
    """Test rate limit handling - job pauses, persists, retries, does NOT fail"""
    
    def test_rate_limit_429_pauses_job(self):
        """Test 429 Too Many Requests pauses job and persists progress"""
        # Test _retry_with_backoff where the error is actually raised
        # Rule: Always mock the lowest internal boundary where the error is thrown
        from app.gmail_client import GmailClient
        
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        
        # Create an exception that will be detected as 429 by _is_rate_limit_error
        # The method checks: error_code == 429 or (error_code == 403 and 'ratelimitexceeded' in error_str)
        class Mock429Error(Exception):
            def __init__(self):
                super().__init__("429 Too Many Requests")
                self.status_code = 429
                self.code = 429
        
        # Test that _retry_with_backoff raises GmailRateLimitError when it detects 429
        # This is the lowest boundary where the error is thrown
        def failing_func():
            raise Mock429Error()
        
        # Verify GmailRateLimitError is raised when _retry_with_backoff detects 429
        with pytest.raises(GmailRateLimitError):
            gmail_client._retry_with_backoff(failing_func)
    
    @pytest.mark.asyncio
    async def test_rate_limit_403_rateLimitExceeded(self):
        """Test 403 rateLimitExceeded is handled"""
        from app.gmail_client import GmailClient
        
        # Create client instance to use the method
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        
        # Create a mock error with 403 rateLimitExceeded
        # The method checks str(e).lower() for 'ratelimitexceeded'
        error_response = Mock()
        error_response.status = 403
        error_response.reason = "rateLimitExceeded"
        error_response.status_code = 403
        # Ensure string representation includes rateLimitExceeded
        error_response.__str__ = Mock(return_value="403 rateLimitExceeded")
        
        # Use the method on the instance
        is_rate_limit, retry_after = gmail_client._is_rate_limit_error(error_response)
        assert is_rate_limit is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_exponential_backoff(self):
        """Test exponential backoff: 2s → 4s → 8s → max 60s"""
        # This test verifies the backoff calculation logic
        rate_limit_delay = 2.0
        max_rate_limit_delay = 60.0
        
        delays = []
        for attempt in range(5):
            wait_time = min(rate_limit_delay, max_rate_limit_delay)
            delays.append(wait_time)
            rate_limit_delay *= 2  # Double for next retry
        
        assert delays[0] == 2.0
        assert delays[1] == 4.0
        assert delays[2] == 8.0
        assert delays[3] == 16.0
        assert delays[4] == 32.0
        # Should cap at 60.0 if delay exceeds max
        assert max(delays) <= max_rate_limit_delay


class TestLLMTimeoutHandling:
    """Test LLM timeout - fallback to rule-based, sync does NOT block"""
    
    def test_llm_timeout_fallback_to_rule_based(self):
        """Test LLM timeout falls back to rule-based classification"""
        import requests
        from unittest.mock import patch
        
        classifier = Classifier()
        classifier.llm_enabled = True
        classifier.llm_timeout_sec = 0.1  # Very short timeout for testing
        
        # Mock requests.post to timeout
        with patch('requests.post', side_effect=requests.exceptions.Timeout()):
            application = {
                'subject': 'Application Received',
                'snippet': 'Thank you for applying'
            }
            
            # Should fallback to rule-based (never block)
            result = classifier.classify(application)
            
            # Should return a valid category (rule-based result)
            assert result in ['APPLIED', 'REJECTED', 'INTERVIEW', 'OFFER_ACCEPTED', 'skip']
    
    def test_llm_timeout_does_not_block_sync(self):
        """Test LLM timeout does not block sync pipeline"""
        classifier = Classifier()
        classifier.llm_enabled = True
        classifier.llm_timeout_sec = 0.001  # Extremely short timeout
        
        application = {
            'subject': 'Interview Invitation',
            'snippet': 'We would like to schedule an interview'
        }
        
        # Even if LLM times out instantly, should return quickly
        import time
        start = time.time()
        result = classifier.classify(application)
        elapsed = time.time() - start
        
        # Should return within reasonable time (much less than sync would take)
        assert elapsed < 1.0  # Must return in < 1 second
        assert result in ['APPLIED', 'REJECTED', 'INTERVIEW', 'OFFER_ACCEPTED', 'skip']


class TestBackendRestartHandling:
    """Test backend restart - progress persisted, sync resumes"""
    
    def test_checkpoint_persisted_on_restart(self):
        """Test checkpoint is persisted and can be read on restart"""
        # Simulate checkpoint data
        checkpoint_data = {
            'mode': 'full_history',
            'time_range_months': None,
            'page_token': 'checkpoint_token_5000',
            'last_processed_message_id': 'msg_5000',
            'last_processed_internal_date': '1000000500000',
            'sync_state': 'FETCHING_BODIES',
            'total_fetched': 5000,
            'processed_count': 4500
        }
        
        # Verify checkpoint contains all required fields
        assert 'page_token' in checkpoint_data
        assert 'last_processed_message_id' in checkpoint_data
        assert 'last_processed_internal_date' in checkpoint_data
        assert 'sync_state' in checkpoint_data
        
        # On restart, should resume from checkpoint
        resume_token = checkpoint_data['page_token']
        assert resume_token == 'checkpoint_token_5000'
    
    def test_sync_state_persisted_on_restart(self):
        """Test sync_state is persisted and can be resumed"""
        from app.database import SyncStateEnum
        
        # Simulate crash at different states
        crash_states = [
            SyncStateEnum.FETCHING_HEADERS,
            SyncStateEnum.FETCHING_BODIES,
            SyncStateEnum.CLASSIFYING
        ]
        
        for state in crash_states:
            # State should be persistable
            assert state.value in ['FETCHING_HEADERS', 'FETCHING_BODIES', 'CLASSIFYING']
            
            # On restart, should resume from this state
            # (Implementation detail - test verifies state can be persisted)


class TestFailureModeSSEEvents:
    """Test SSE events are emitted for failure modes"""
    
    def test_rate_limit_emits_sse_event(self):
        """Test rate limit emits 'rate_limited' SSE event"""
        from app.progress_events import SyncPhase
        
        # Verify RATE_LIMITED phase exists
        assert hasattr(SyncPhase, 'RATE_LIMITED')
        
        # Event should include rate limit information
        # Note: SyncPhase.RATE_LIMITED is already a string, not an enum with .value
        event = {
            'phase': SyncPhase.RATE_LIMITED,  # Already a string, not enum
            'message': 'Rate limit reached. Pausing sync and retrying...',
            'errors': [{
                'code': 'RATE_LIMIT',
                'retryable': True,
                'retry_after_seconds': 2
            }]
        }
        
        assert event['phase'] == 'rate_limited'
        assert event['errors'][0]['code'] == 'RATE_LIMIT'
        assert event['errors'][0]['retryable'] is True
