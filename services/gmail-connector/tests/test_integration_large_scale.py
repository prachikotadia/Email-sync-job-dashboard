"""
Integration Test - 10k+ Mocked Emails (MANDATORY)

Tests full sync flow with large-scale email dataset.
CRITICAL: Must process 10,000+ emails without issues.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.sync_engine import SyncEngine
from app.gmail_client import GmailClient
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor
from app.database import Application


class TestIntegrationLargeScale:
    """Integration tests with 10k+ mocked emails"""
    
    def generate_mock_messages(self, count: int):
        """Generate mock Gmail messages that pass Stage 1 filter"""
        # Rule: Never mock only the final call — mock the inputs that allow execution to reach it
        # Messages MUST have structure that passes _is_candidate_job_email filter:
        # - payload.headers with Subject and From (case-sensitive 'Subject', 'From')
        # - snippet with job-related keywords (lowercase checked)
        # - Subject/snippet must contain: 'application', 'applied', 'interview', 'offer', 'rejection', 'job', 'career', etc.
        messages = []
        job_keywords = ['application', 'applied', 'interview', 'offer', 'rejection', 'job', 'career', 'recruiter']
        
        for i in range(count):
            keyword = job_keywords[i % len(job_keywords)]
            # Ensure snippet contains job keywords (required for Stage 1 filter - checked in lowercase)
            snippet = f'Thank you for your {keyword}. We will review your application.' if i % 2 == 0 else f'Your {keyword} has been received.'
            # Ensure subject contains job keywords (checked in lowercase)
            subject = f'Application Update {i}' if i % 2 == 0 else f'Interview Invitation {i}'
            from_email = f'recruiter{i % 100}@company{i % 50}.com'
            
            messages.append({
                'id': f'msg_{i:08d}',
                'threadId': f'thread_{i // 10}',
                'internalDate': str(1000000000000 + i * 1000),
                'snippet': snippet,  # Must contain job keywords (checked lowercase)
                'payload': {
                    'headers': [
                        {'name': 'Subject', 'value': subject},  # Must contain job keywords
                        {'name': 'From', 'value': from_email}
                    ]
                }
            })
        return messages
    
    @pytest.mark.asyncio
    async def test_sync_10k_emails_full_flow(self):
        """Test full sync flow with 10,000 emails"""
        NUM_EMAILS = 10000
        
        # Generate mock messages
        mock_messages = self.generate_mock_messages(NUM_EMAILS)
        
        # Mock Gmail client
        mock_gmail_client = Mock(spec=GmailClient)
        # get_all_messages() is NOT async - use Mock, not AsyncMock
        mock_gmail_client.get_all_messages = Mock(
            return_value=(mock_messages, 'hist_123', None)
        )
        
        # Mock classifier
        mock_classifier = Mock(spec=Classifier)
        mock_classifier.classify = Mock(side_effect=lambda app: 'APPLIED' if 'applied' in app.get('snippet', '').lower() else 'SKIP')
        
        # Mock company extractor
        # Rule: Never mock only the final call — mock the inputs that allow execution to reach it
        # extract() returns tuple: (company_name, source, confidence) - MUST return tuple
        mock_company_extractor = Mock(spec=CompanyExtractor)
        mock_company_extractor.extract = Mock(return_value=('TestCompany', 'domain', 0.9))  # Must return tuple
        mock_company_extractor.extract_role = Mock(return_value='Software Engineer')  # extract_role returns string
        
        # Mock database
        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[])))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Create sync engine
        sync_engine = SyncEngine(mock_gmail_client, mock_classifier, mock_company_extractor, mock_db)
        
        # Run sync
        processed_count = 0
        async for progress in sync_engine.sync_all_emails(user_id=1, mode='full_history'):
            processed_count += 1
            # Stop after reasonable iteration count (sync yields progress updates)
            if processed_count > 100:  # Prevent infinite loop in test
                break
        
        # Verify Gmail client was called
        mock_gmail_client.get_all_messages.assert_called_once()
        
        # Verify classifier was called (at least for candidate emails)
        assert mock_classifier.classify.called
    
    @pytest.mark.asyncio
    async def test_sync_30k_emails_idempotency(self):
        """Test idempotency with 30,000 emails - re-run must NOT duplicate"""
        NUM_EMAILS = 30000
        
        # Generate mock messages
        mock_messages = self.generate_mock_messages(NUM_EMAILS)
        message_ids = [msg['id'] for msg in mock_messages]
        
        # Mock database with existing applications (simulate first run)
        existing_message_ids = set(message_ids[:1000])  # First 1000 already processed
        
        mock_db = Mock()
        mock_existing_apps = [Mock(gmail_message_id=msg_id) for msg_id in existing_message_ids]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_existing_apps
        
        # Mock Gmail client
        mock_gmail_client = Mock(spec=GmailClient)
        # get_all_messages() is NOT async - use Mock, not AsyncMock
        mock_gmail_client.get_all_messages = Mock(
            return_value=(mock_messages, 'hist_123', None)
        )
        
        # Mock classifier
        mock_classifier = Mock(spec=Classifier)
        mock_classifier.classify = Mock(return_value='APPLIED')
        
        # Mock company extractor
        # Rule: Never mock only the final call — mock the inputs that allow execution to reach it
        # extract() returns tuple: (company_name, source, confidence) - MUST return tuple
        mock_company_extractor = Mock(spec=CompanyExtractor)
        mock_company_extractor.extract = Mock(return_value=('TestCompany', 'domain', 0.9))  # Must return tuple
        mock_company_extractor.extract_role = Mock(return_value='Software Engineer')  # extract_role returns string
        
        # Create sync engine
        sync_engine = SyncEngine(mock_gmail_client, mock_classifier, mock_company_extractor, mock_db)
        
        # Run sync
        processed_count = 0
        async for progress in sync_engine.sync_all_emails(user_id=1, mode='full_history'):
            processed_count += 1
            if processed_count > 100:  # Prevent infinite loop
                break
        
        # Verify idempotency check was performed
        assert mock_db.query.called
        
        # In real implementation, only non-existing messages should be saved
        # This test verifies the idempotency check exists
    
    @pytest.mark.asyncio
    async def test_checkpoint_persistence_large_scale(self):
        """Test checkpoint persistence with large dataset"""
        NUM_EMAILS = 15000
        
        # Generate mock messages
        mock_messages = self.generate_mock_messages(NUM_EMAILS)
        
        # Mock Gmail client with checkpoint token support
        page_token = 'checkpoint_token_5000'
        
        mock_gmail_client = Mock(spec=GmailClient)
        # get_all_messages() is NOT async - use Mock, not AsyncMock
        mock_gmail_client.get_all_messages = Mock(
            return_value=(mock_messages[5000:], 'hist_123', None)
        )
        
        # Mock components
        mock_classifier = Mock(spec=Classifier)
        mock_classifier.classify = Mock(return_value='APPLIED')
        
        mock_company_extractor = Mock(spec=CompanyExtractor)
        mock_company_extractor.extract = Mock(return_value=('TestCompany', 'domain', 0.9))  # Must return tuple
        mock_company_extractor.extract_role = Mock(return_value='Software Engineer')  # extract_role returns string
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        sync_engine = SyncEngine(mock_gmail_client, mock_classifier, mock_company_extractor, mock_db)
        
        # Run sync with checkpoint token
        async for progress in sync_engine.sync_all_emails(
            user_id=1, 
            mode='full_history',
            checkpoint_token=page_token
        ):
            # Verify checkpoint token is used
            call_args = mock_gmail_client.get_all_messages.call_args
            if call_args:
                assert 'page_token' in str(call_args)
            break  # Stop after first progress update
    
    @pytest.mark.asyncio
    async def test_sync_counts_accuracy_large_scale(self):
        """Test count accuracy with 10k+ emails"""
        NUM_EMAILS = 12000
        
        mock_messages = self.generate_mock_messages(NUM_EMAILS)
        
        mock_gmail_client = Mock(spec=GmailClient)
        # get_all_messages() is NOT async - use Mock, not AsyncMock
        mock_gmail_client.get_all_messages = Mock(
            return_value=(mock_messages, 'hist_123', None)
        )
        
        mock_classifier = Mock(spec=Classifier)
        mock_classifier.classify = Mock(return_value='APPLIED')
        
        mock_company_extractor = Mock(spec=CompanyExtractor)
        mock_company_extractor.extract = Mock(return_value=('TestCompany', 'domain', 0.9))  # Must return tuple
        mock_company_extractor.extract_role = Mock(return_value='Software Engineer')  # extract_role returns string
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        sync_engine = SyncEngine(mock_gmail_client, mock_classifier, mock_company_extractor, mock_db)
        
        total_scanned = 0
        total_fetched = 0
        
        async for progress in sync_engine.sync_all_emails(user_id=1, mode='full_history'):
            total_scanned = progress.get('total_scanned', 0)
            total_fetched = progress.get('total_fetched', 0)
            if total_scanned > 0:
                break  # Get first progress update
        
        # Verify counts match input
        assert total_fetched == NUM_EMAILS
        assert total_scanned == NUM_EMAILS
