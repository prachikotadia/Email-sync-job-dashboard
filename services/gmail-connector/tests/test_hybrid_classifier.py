"""
Comprehensive test suite for 9-Layer Hybrid Email Classification Engine.

Tests cover all 9 layers:
1. Hard Ignore Filter
2. Thread Context Analyzer
3. Sender Intelligence Engine
4. Structural Email Parsing
5. Rule-Based Engine
6. Statistical Confidence Scoring
7. Local LLM Semantic Classifier
8. Deterministic Resolver
9. Trace Logger + Explanation
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.hybrid_classifier import (
    HybridClassifier,
    ClassificationStatus,
    SenderType,
    ClassificationSignals,
    ClassificationResult
)


class TestLayer1HardIgnore:
    """Test Layer 1: Hard Ignore Filter"""
    
    def test_job_board_spam_filtered(self):
        """Test that job board emails are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "New jobs for you",
            "snippet": "Check out these opportunities",
            "sender_domain": "linkedin.com",
            "sender_email": "notifications@linkedin.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
        assert "job_board" in result.signals.signals_used or "promo" in result.signals.signals_used
    
    def test_promo_domain_filtered(self):
        """Test promotional domains are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Special Offer",
            "snippet": "Limited time deal",
            "sender_domain": "noreply.shop.com",
            "sender_email": "noreply@shop.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
    
    def test_unsubscribe_pattern_filtered(self):
        """Test unsubscribe patterns are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Newsletter",
            "snippet": "Click here to unsubscribe from our mailing list",
            "sender_domain": "company.com",
            "sender_email": "newsletter@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE


class TestLayer2ThreadContext:
    """Test Layer 2: Thread Context Analyzer"""
    
    def test_thread_rejection_detected(self):
        """Test that thread rejection is detected"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        mock_thread = {
            'messages': [
                {
                    'internalDate': '1000000',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Rejection'},
                            {'name': 'From', 'value': 'hr@company.com'},
                            {'name': 'Date', 'value': 'Mon, 1 Jan 2024'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Follow up",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        # Thread context should influence classification
        assert "thread_context" in result.signals.signals_used


class TestLayer3SenderIntelligence:
    """Test Layer 3: Sender Intelligence Engine"""
    
    def test_ats_domain_detected(self):
        """Test ATS domains are identified"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "sender_domain": "greenhouse.io",
            "sender_email": "noreply@greenhouse.io"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_type == SenderType.ATS
        assert result.signals.sender_confidence > 0.8
    
    def test_company_domain_detected(self):
        """Test company domains are identified"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Offer",
            "snippet": "We'd like to offer",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_type == SenderType.COMPANY
        assert result.signals.sender_confidence > 0.8


class TestLayer4StructuralParsing:
    """Test Layer 4: Structural Email Parsing"""
    
    def test_calendar_invite_detected(self):
        """Test calendar invites are detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview Invitation",
            "snippet": "Please add this to your calendar",
            "body": "Click here to add to Google Calendar",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.has_calendar_invite
        assert "calendar_invite" in result.signals.signals_used
    
    def test_date_time_mentioned(self):
        """Test date/time mentions are detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Monday, January 15th at 2:00 PM",
            "body": "We'd like to schedule for Monday, January 15th at 2:00 PM",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.has_date_mention
        assert result.signals.has_time_mention


class TestLayer5RuleEngine:
    """Test Layer 5: Rule-Based Engine"""
    
    def test_rejected_rule_matches(self):
        """Test rejection rules match"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Application Update",
            "snippet": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.REJECTED
        assert len(result.signals.matched_rules) > 0
        assert "REJECTED" in str(result.signals.rules_triggered)
    
    def test_interview_rule_matches(self):
        """Test interview rules match"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview Scheduling",
            "snippet": "We would like to schedule a technical interview",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.INTERVIEW
        assert "INTERVIEW" in str(result.signals.rules_triggered)
    
    def test_offer_rule_matches(self):
        """Test offer rules match"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Job Offer",
            "snippet": "We are pleased to offer you the position with a salary of $100k",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.OFFER
        assert "OFFER" in str(result.signals.rules_triggered)


class TestLayer6ConfidenceScoring:
    """Test Layer 6: Statistical Confidence Scoring"""
    
    def test_confidence_calculated(self):
        """Test that confidence is calculated from all layers"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview for Monday at 2 PM",
            "body": "Add to calendar",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com"
        }
        
        result = classifier.classify(email_data)
        assert result.confidence > 0.0
        assert result.confidence <= 1.0
        assert result.signals.final_confidence > 0.0
    
    def test_multiple_signals_boost_confidence(self):
        """Test that multiple signals boost confidence"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview Invitation",
            "snippet": "Schedule your technical interview for Monday, January 15th at 2:00 PM. Add to calendar.",
            "body": "Calendar invite attached",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com"
        }
        
        result = classifier.classify(email_data)
        # Multiple signals should boost confidence
        assert result.confidence >= 0.8


class TestLayer7LLM:
    """Test Layer 7: Local LLM Semantic Classifier"""
    
    @pytest.mark.asyncio
    async def test_llm_called_when_confidence_low(self):
        """Test LLM is called when confidence is below threshold"""
        classifier = HybridClassifier()
        classifier.llm_enabled = True
        classifier.confidence_threshold = 0.9  # High threshold to force LLM
        
        mock_response = {
            "response": '{"status": "ACTIVE", "confidence": 0.85, "reason": "Application confirmation"}'
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value.status = 200
            mock_post.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            mock_session.return_value.post.return_value = mock_post
            
            email_data = {
                "subject": "Thank you",
                "snippet": "We have received your application",
                "sender_domain": "company.com",
                "sender_email": "hr@company.com"
            }
            
            result = classifier.classify(email_data)
            # LLM should be used if confidence is low
            # Note: This is a simplified test - actual LLM integration needs proper mocking


class TestLayer8DeterministicResolver:
    """Test Layer 8: Deterministic Resolver"""
    
    def test_thread_rejection_overrides(self):
        """Test that thread rejection overrides other classifications"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        mock_thread = {
            'messages': [
                {
                    'internalDate': '1000000',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Rejection - Unfortunately'},
                            {'name': 'From', 'value': 'hr@company.com'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Follow up",
            "snippet": "Thank you for your interest",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        # Thread rejection should override
        assert result.status == ClassificationStatus.REJECTED
    
    def test_priority_order_respected(self):
        """Test that priority order is respected"""
        classifier = HybridClassifier()
        
        # Email with both rejection and interview keywords
        email_data = {
            "subject": "Interview - Unfortunately Not Selected",
            "snippet": "We regret to inform you that we cannot proceed with the interview",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        # REJECTED should have higher priority than INTERVIEW
        assert result.status == ClassificationStatus.REJECTED


class TestLayer9TraceLogger:
    """Test Layer 9: Trace Logger + Explanation"""
    
    def test_explanation_generated(self):
        """Test that explanation is generated"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Rejection",
            "snippet": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.explanation
        assert len(result.explanation) > 0
        assert result.signals.signals_used
        assert result.signals.rules_triggered
    
    def test_trace_dict_generated(self):
        """Test that trace dictionary is generated"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        trace_dict = result.to_dict()
        
        assert "final_status" in trace_dict
        assert "confidence" in trace_dict
        assert "signals_used" in trace_dict
        assert "rules_triggered" in trace_dict
        assert "llm_used" in trace_dict
        assert "explanation" in trace_dict
        assert "version" in trace_dict


class TestEdgeCases:
    """Test Edge Cases"""
    
    def test_empty_fields_handled(self):
        """Test that empty fields are handled gracefully"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "",
            "snippet": "",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status in [ClassificationStatus.ACTIVE, ClassificationStatus.IGNORE]
    
    def test_missing_fields_handled(self):
        """Test that missing fields are handled"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Test"
        }
        
        result = classifier.classify(email_data)
        assert result is not None
        assert result.status is not None


class TestPerformance:
    """Test Performance"""
    
    def test_deterministic_output(self):
        """Test that same email produces same classification"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result1 = classifier.classify(email_data)
        result2 = classifier.classify(email_data)
        
        assert result1.status == result2.status
        assert result1.confidence == result2.confidence
        assert result1.signals.signals_used == result2.signals.signals_used
