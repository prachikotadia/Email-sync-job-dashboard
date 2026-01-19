"""
Unit Tests - Pagination Loop (MANDATORY)

Tests pagination logic to ensure all emails are fetched.
CRITICAL: Pagination must continue until nextPageToken is null.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.gmail_client import GmailClient


class TestPaginationLoop:
    """Test pagination loop continues until nextPageToken is null"""
    
    def test_pagination_completes_all_pages(self):
        """Test pagination fetches all pages until nextPageToken is null"""
        # Pagination mocks MUST be stateful - return different responses per call
        # Rule: Pagination mocks must be stateful, never static
        pages = [
            {
                'messages': [{'id': f'msg_{i}'} for i in range(500)],
                'nextPageToken': 'token_page_2',
                'historyId': 'hist_1'
            },
            {
                'messages': [{'id': f'msg_{i+500}'} for i in range(500)],
                'nextPageToken': 'token_page_3',
                'historyId': 'hist_1'
            },
            {
                'messages': [{'id': f'msg_{i+1000}'} for i in range(300)],
                'nextPageToken': None,  # Final page - MUST be None
                'historyId': 'hist_1'
            }
        ]
        
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        gmail_client.service = Mock()
        
        # Stateful mock: returns different page per list call, message data per get call
        # Rule: Pagination mocks must be stateful, never static
        list_call_count = 0
        get_call_count = 0
        def mock_retry_with_backoff(func, max_attempts=6, initial_delay=1.0, max_delay=60.0):
            nonlocal list_call_count, get_call_count
            # Call the function - it will try to access service.users().messages().list() or .get()
            try:
                result = func()
                # If result has 'messages' key, it's a list_page result
                if isinstance(result, dict) and 'messages' in result:
                    if list_call_count < len(pages):
                        result = pages[list_call_count]
                        list_call_count += 1
                        return result
                    return {'messages': [], 'nextPageToken': None, 'historyId': 'hist_1'}
                # Otherwise it's a message result
                return result
            except (AttributeError, TypeError):
                # func raises because service chain isn't complete
                # We need to detect by checking what the func tries to access
                # For now, use call order: first calls are list, later calls are get
                # But we need to track separately
                func_code = str(func.__code__) if hasattr(func, '__code__') else str(func)
                if 'list' in func_code.lower() or (list_call_count < len(pages) and get_call_count == 0):
                    # This is likely a list_page call (happens first)
                    if list_call_count < len(pages):
                        result = pages[list_call_count]
                        list_call_count += 1
                        return result
                    return {'messages': [], 'nextPageToken': None, 'historyId': 'hist_1'}
                else:
                    # This is likely a get_message call
                    get_call_count += 1
                    return {'id': f'msg_{get_call_count}', 'threadId': 'thread_1', 'internalDate': '1000000'}
        
        # Mock the service chain to allow func() to execute
        mock_list_execute = Mock(side_effect=lambda: pages[list_call_count] if list_call_count < len(pages) else {'messages': [], 'nextPageToken': None})
        mock_get_execute = Mock(return_value={'id': 'msg_1', 'threadId': 'thread_1', 'internalDate': '1000000'})
        mock_messages = Mock()
        mock_messages.list.return_value.execute = mock_list_execute
        mock_messages.get.return_value.execute = mock_get_execute
        mock_users = Mock()
        mock_users.messages.return_value = mock_messages
        gmail_client.service.users.return_value = mock_users
        
        with patch.object(gmail_client, '_retry_with_backoff', side_effect=mock_retry_with_backoff):
            messages, history_id, next_token = gmail_client.get_all_messages()
        
        # Verify all messages fetched (500 + 500 + 300 = 1300)
        assert len(messages) == 1300
        assert next_token is None  # Must be None on completion
        assert list_call_count == 3  # Should fetch 3 pages
    
    @pytest.mark.asyncio
    async def test_pagination_handles_empty_results(self):
        """Test pagination handles empty message list gracefully"""
        mock_response = {
            'messages': [],
            'nextPageToken': None,
            'historyId': 'hist_1'
        }
        
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        gmail_client.service = Mock()
        
        with patch.object(gmail_client, '_retry_with_backoff', return_value=mock_response):
            messages, history_id, next_token = gmail_client.get_all_messages()  # NOT async - remove await
        
        assert len(messages) == 0
        assert next_token is None
    
    @pytest.mark.asyncio
    async def test_pagination_resume_from_checkpoint(self):
        """Test pagination can resume from checkpoint token"""
        mock_responses = [
            {
                'messages': [{'id': f'msg_{i+500}'} for i in range(500)],
                'nextPageToken': None,
                'historyId': 'hist_1'
            }
        ]
        
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        gmail_client.service = Mock()
        
        with patch.object(gmail_client, '_retry_with_backoff', return_value=mock_responses[0]):
            with patch.object(gmail_client.service.users().messages(), 'get', return_value=Mock(execute=lambda: {'id': 'msg_1'})):
                messages, history_id, next_token = gmail_client.get_all_messages(page_token='token_page_2')  # NOT async
        
        # Should use checkpoint token and resume
        assert len(messages) == 500
        assert next_token is None
    
    def test_pagination_10k_messages(self):
        """Test pagination handles 10k+ messages across multiple pages"""
        # Simulate 10,500 messages (21 pages of 500)
        # Pagination mocks MUST be stateful - return different responses per call
        num_pages = 21
        total_messages = 10500
        
        pages = []
        for page in range(num_pages):
            page_start = page * 500
            page_end = min(page_start + 500, total_messages)
            pages.append({
                'messages': [{'id': f'msg_{i}'} for i in range(page_start, page_end)],
                'nextPageToken': f'token_page_{page+2}' if page < num_pages - 1 else None,
                'historyId': 'hist_1'
            })
        
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        gmail_client.service = Mock()
        
        # Stateful mock: returns different page per list call, message data per get call
        # Rule: Pagination mocks must be stateful, never static
        list_call_count = 0
        get_call_count = 0
        def mock_retry_with_backoff(func, max_attempts=6, initial_delay=1.0, max_delay=60.0):
            nonlocal list_call_count, get_call_count
            # Call the function - it will try to access service.users().messages().list() or .get()
            try:
                result = func()
                # If result has 'messages' key, it's a list_page result
                if isinstance(result, dict) and 'messages' in result:
                    if list_call_count < len(pages):
                        result = pages[list_call_count]
                        list_call_count += 1
                        return result
                    return {'messages': [], 'nextPageToken': None, 'historyId': 'hist_1'}
                # Otherwise it's a message result
                return result
            except (AttributeError, TypeError):
                # func raises because service chain isn't complete
                # Use call order: first calls are list, later calls are get
                func_code = str(func.__code__) if hasattr(func, '__code__') else str(func)
                if 'list' in func_code.lower() or (list_call_count < len(pages) and get_call_count == 0):
                    # This is likely a list_page call (happens first)
                    if list_call_count < len(pages):
                        result = pages[list_call_count]
                        list_call_count += 1
                        return result
                    return {'messages': [], 'nextPageToken': None, 'historyId': 'hist_1'}
                else:
                    # This is likely a get_message call
                    get_call_count += 1
                    return {'id': f'msg_{get_call_count}', 'threadId': 'thread_1', 'internalDate': '1000000'}
        
        # Mock the service chain to allow func() to execute
        # Create stateful execute functions that return different pages
        list_execute_call_count = [0]  # Use list to allow modification in nested function
        def mock_list_execute():
            if list_execute_call_count[0] < len(pages):
                result = pages[list_execute_call_count[0]]
                list_execute_call_count[0] += 1
                return result
            return {'messages': [], 'nextPageToken': None}
        
        mock_get_execute = Mock(return_value={'id': 'msg_1', 'threadId': 'thread_1', 'internalDate': '1000000'})
        mock_messages = Mock()
        mock_messages.list.return_value.execute = mock_list_execute
        mock_messages.get.return_value.execute = mock_get_execute
        mock_users = Mock()
        mock_users.messages.return_value = mock_messages
        gmail_client.service.users.return_value = mock_users
        
        # Update list_call_count from the execute function
        def update_list_count():
            nonlocal list_call_count
            list_call_count = list_execute_call_count[0]
        
        with patch.object(gmail_client, '_retry_with_backoff', side_effect=mock_retry_with_backoff):
            messages, history_id, next_token = gmail_client.get_all_messages()
        
        assert len(messages) == total_messages
        assert next_token is None
        assert list_call_count == num_pages  # Should fetch all pages
    
    @pytest.mark.asyncio
    async def test_pagination_boundary_500_messages(self):
        """Test pagination handles exactly 500 messages (boundary condition)"""
        # Exactly 500 messages - one full page, nextPageToken is None
        mock_response = {
            'messages': [{'id': f'msg_{i}'} for i in range(500)],
            'nextPageToken': None,  # Must be None even with full page
            'historyId': 'hist_1'
        }
        
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        gmail_client.service = Mock()
        
        with patch.object(gmail_client, '_retry_with_backoff', return_value=mock_response):
            with patch.object(gmail_client.service.users().messages(), 'get', return_value=Mock(execute=lambda: {'id': 'msg_1'})):
                messages, history_id, next_token = gmail_client.get_all_messages()  # NOT async - remove await
        
        assert len(messages) == 500
        assert next_token is None  # Must stop when nextPageToken is None
    
    def test_pagination_never_stops_early(self):
        """Test pagination never stops before nextPageToken is null"""
        # Pagination mocks MUST be stateful - return different responses per call
        # Rule: Pagination mocks must be stateful, never static
        pages = [
            {
                'messages': [{'id': f'msg_{i}'} for i in range(500)],
                'nextPageToken': 'token_page_2',
                'historyId': 'hist_1'
            },
            {
                'messages': [{'id': f'msg_{i+500}'} for i in range(100)],  # Last page < 500
                'nextPageToken': None,  # Must continue until this is None
                'historyId': 'hist_1'
            }
        ]
        
        gmail_client = GmailClient(user_id=1, user_email="test@example.com", oauth_token=Mock())
        gmail_client.service = Mock()
        
        # Stateful mock: returns different page per list call, message data per get call
        # Rule: Pagination mocks must be stateful, never static
        list_call_count = 0
        get_call_count = 0
        def mock_retry_with_backoff(func, max_attempts=6, initial_delay=1.0, max_delay=60.0):
            nonlocal list_call_count, get_call_count
            # Call the function - it will try to access service.users().messages().list() or .get()
            try:
                result = func()
                # If result has 'messages' key, it's a list_page result
                if isinstance(result, dict) and 'messages' in result:
                    if list_call_count < len(pages):
                        result = pages[list_call_count]
                        list_call_count += 1
                        return result
                    return {'messages': [], 'nextPageToken': None, 'historyId': 'hist_1'}
                # Otherwise it's a message result
                return result
            except (AttributeError, TypeError):
                # func raises because service chain isn't complete
                # Use call order: first calls are list, later calls are get
                func_code = str(func.__code__) if hasattr(func, '__code__') else str(func)
                if 'list' in func_code.lower() or (list_call_count < len(pages) and get_call_count == 0):
                    # This is likely a list_page call (happens first)
                    if list_call_count < len(pages):
                        result = pages[list_call_count]
                        list_call_count += 1
                        return result
                    return {'messages': [], 'nextPageToken': None, 'historyId': 'hist_1'}
                else:
                    # This is likely a get_message call
                    get_call_count += 1
                    return {'id': f'msg_{get_call_count}', 'threadId': 'thread_1', 'internalDate': '1000000'}
        
        # Mock the service chain to allow func() to execute
        # Create stateful execute functions that return different pages
        list_execute_call_count = [0]  # Use list to allow modification in nested function
        def mock_list_execute():
            if list_execute_call_count[0] < len(pages):
                result = pages[list_execute_call_count[0]]
                list_execute_call_count[0] += 1
                return result
            return {'messages': [], 'nextPageToken': None}
        
        mock_get_execute = Mock(return_value={'id': 'msg_1', 'threadId': 'thread_1', 'internalDate': '1000000'})
        mock_messages = Mock()
        mock_messages.list.return_value.execute = mock_list_execute
        mock_messages.get.return_value.execute = mock_get_execute
        mock_users = Mock()
        mock_users.messages.return_value = mock_messages
        gmail_client.service.users.return_value = mock_users
        
        # Update list_call_count from the execute function
        def update_list_count():
            nonlocal list_call_count
            list_call_count = list_execute_call_count[0]
        
        with patch.object(gmail_client, '_retry_with_backoff', side_effect=mock_retry_with_backoff):
            messages, history_id, next_token = gmail_client.get_all_messages()
            update_list_count()  # Sync the count
        
        # Should fetch all messages (500 + 100 = 600)
        assert len(messages) == 600
        assert next_token is None
        assert list_call_count == 2  # Should fetch both pages
