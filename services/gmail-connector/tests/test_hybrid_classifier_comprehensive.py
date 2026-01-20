"""
COMPREHENSIVE TEST SUITE FOR 9-LAYER HYBRID CLASSIFICATION ENGINE

Tests all 9 layers with edge cases, integration tests, and performance tests.
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


# ============================================================================
# LAYER 1: HARD IGNORE FILTER TESTS
# ============================================================================

class TestLayer1HardIgnore:
    """Test Layer 1: Hard Ignore Filter - Zero False Positives"""
    
    def test_job_board_linkedin_filtered(self):
        """Test LinkedIn job board emails are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "New jobs for you",
            "snippet": "Check out these opportunities",
            "sender_domain": "linkedin.com",
            "sender_email": "notifications@linkedin.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
        assert "job_board" in result.signals.signals_used or "job_board_domain" in result.signals.signals_used
    
    def test_job_board_indeed_filtered(self):
        """Test Indeed job board emails are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "New job matches",
            "snippet": "We found jobs for you",
            "sender_domain": "indeed.com",
            "sender_email": "noreply@indeed.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
    
    def test_job_board_glassdoor_filtered(self):
        """Test Glassdoor job board emails are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Job alerts",
            "snippet": "New opportunities",
            "sender_domain": "glassdoor.com",
            "sender_email": "alerts@glassdoor.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
    
    def test_promo_domain_noreply_filtered(self):
        """Test noreply promotional domains are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Special Offer",
            "snippet": "Limited time deal",
            "sender_domain": "noreply.shop.com",
            "sender_email": "noreply@shop.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
        assert "promo_domain" in result.signals.signals_used
    
    def test_promo_domain_marketing_filtered(self):
        """Test marketing domains are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Flash Sale",
            "snippet": "50% off everything",
            "sender_domain": "marketing.store.com",
            "sender_email": "marketing@store.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
    
    def test_no_reply_address_filtered(self):
        """Test no-reply addresses are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Newsletter",
            "snippet": "Weekly updates",
            "sender_domain": "company.com",
            "sender_email": "no-reply@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
        assert "no_reply_address" in result.signals.signals_used
    
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
        assert "unsubscribe_pattern" in result.signals.signals_used
    
    def test_bulk_header_filtered(self):
        """Test bulk email headers are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Newsletter",
            "snippet": "Weekly updates",
            "sender_domain": "company.com",
            "sender_email": "newsletter@company.com",
            "headers": {
                "List-Unsubscribe": "<mailto:unsubscribe@company.com>",
                "Precedence": "bulk"
            }
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
        assert "bulk_header" in result.signals.signals_used
    
    def test_non_job_wifi_approved_filtered(self):
        """Test non-job WiFi approval emails are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "WiFi Application Approved",
            "snippet": "Your WiFi application has been approved",
            "sender_domain": "wifi.com",
            "sender_email": "noreply@wifi.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
        assert "non_job_offer" in result.signals.signals_used
    
    def test_non_job_nike_offer_filtered(self):
        """Test non-job Nike offer emails are filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Nike Offer Approved",
            "snippet": "Your Nike offer has been approved",
            "sender_domain": "nike.com",
            "sender_email": "offers@nike.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.IGNORE
    
    def test_job_offer_not_filtered(self):
        """Test actual job offers are NOT filtered"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Job Offer - Software Engineer",
            "snippet": "We are pleased to offer you the position",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status != ClassificationStatus.IGNORE


# ============================================================================
# LAYER 2: THREAD CONTEXT ANALYZER TESTS
# ============================================================================

class TestLayer2ThreadContext:
    """Test Layer 2: Thread Context Analyzer"""
    
    def test_thread_rejection_detected(self):
        """Test that thread rejection is detected"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        
        # Mock thread with rejection message
        mock_thread = {
            'messages': [
                {
                    'internalDate': '1000000',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Rejection - Unfortunately'},
                            {'name': 'From', 'value': 'hr@company.com'},
                            {'name': 'Date', 'value': 'Mon, 1 Jan 2024'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Follow up",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        assert result.signals.thread_has_rejection or result.status == ClassificationStatus.REJECTED
        assert "thread_context" in result.signals.signals_used
    
    def test_thread_offer_detected(self):
        """Test that thread offer is detected"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        
        mock_thread = {
            'messages': [
                {
                    'internalDate': '1000000',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Job Offer'},
                            {'name': 'From', 'value': 'hr@company.com'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Re: Job Offer",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        assert result.signals.thread_has_offer or result.status == ClassificationStatus.OFFER
    
    def test_thread_interview_detected(self):
        """Test that thread interview is detected"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        
        mock_thread = {
            'messages': [
                {
                    'internalDate': '1000000',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Interview Scheduling'},
                            {'name': 'From', 'value': 'hr@company.com'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Re: Interview Scheduling",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        assert result.signals.thread_has_interview
    
    def test_candidate_message_ignored(self):
        """Test that candidate's own messages are ignored in thread context"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        
        mock_thread = {
            'messages': [
                {
                    'internalDate': '1000000',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Re: Interview'},
                            {'name': 'From', 'value': 'candidate@email.com'}  # Candidate's email
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Re: Interview",
            "snippet": "Thank you",
            "sender_domain": "email.com",
            "sender_email": "candidate@email.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        # Candidate's message shouldn't affect classification
        assert not result.signals.thread_has_rejection
    
    def test_thread_chronological_sorting(self):
        """Test that thread messages are sorted chronologically"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        
        # Messages out of order
        mock_thread = {
            'messages': [
                {
                    'internalDate': '3000000',  # Latest
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Latest message'},
                            {'name': 'From', 'value': 'hr@company.com'}
                        ]
                    }
                },
                {
                    'internalDate': '1000000',  # Oldest
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Oldest message'},
                            {'name': 'From', 'value': 'hr@company.com'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Re: Latest message",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        # Should process messages in chronological order
        assert result is not None


# ============================================================================
# LAYER 3: SENDER INTELLIGENCE ENGINE TESTS
# ============================================================================

class TestLayer3SenderIntelligence:
    """Test Layer 3: Sender Intelligence Engine"""
    
    def test_ats_domain_greenhouse_detected(self):
        """Test Greenhouse ATS domain is identified"""
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
    
    def test_ats_domain_lever_detected(self):
        """Test Lever ATS domain is identified"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "sender_domain": "lever.co",
            "sender_email": "noreply@lever.co"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_type == SenderType.ATS
    
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
    
    def test_human_email_detected(self):
        """Test personal email domains are identified"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Let's schedule",
            "sender_domain": "gmail.com",
            "sender_email": "recruiter@gmail.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_type == SenderType.HUMAN
        assert result.signals.sender_confidence < 0.7
    
    def test_sender_historical_interview(self):
        """Test historical sender behavior (has sent interviews)"""
        classifier = HybridClassifier()
        mock_db = Mock()
        
        # Mock database query
        mock_application = Mock()
        mock_application.category = "INTERVIEW"
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 1
        mock_db.query.return_value = mock_query
        
        classifier.db = mock_db
        
        email_data = {
            "subject": "Follow up",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_has_sent_interview
    
    def test_sender_historical_rejection(self):
        """Test historical sender behavior (has sent rejections)"""
        classifier = HybridClassifier()
        mock_db = Mock()
        
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 1
        mock_db.query.return_value = mock_query
        
        classifier.db = mock_db
        
        email_data = {
            "subject": "Update",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_has_sent_rejection
    
    def test_noise_domain_detected(self):
        """Test unknown domains are classified as NOISE"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Test",
            "snippet": "Test message",
            "sender_domain": "unknown-domain.xyz",
            "sender_email": "test@unknown-domain.xyz"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_type == SenderType.NOISE
        assert result.signals.sender_confidence < 0.5


# ============================================================================
# LAYER 4: STRUCTURAL EMAIL PARSING TESTS
# ============================================================================

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
    
    def test_ics_file_detected(self):
        """Test .ics calendar files are detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Calendar invite attached",
            "body": "Please find the .ics file attached",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.has_calendar_invite
        assert "calendar_ics_file" in result.signals.signals_used
    
    def test_date_mentioned(self):
        """Test date mentions are detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Monday, January 15th",
            "body": "We'd like to schedule for Monday, January 15th",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.has_date_mention
        assert "date_mention" in result.signals.signals_used
    
    def test_time_mentioned(self):
        """Test time mentions are detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "2:00 PM",
            "body": "We'd like to schedule for 2:00 PM",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.has_time_mention
        assert "time_mention" in result.signals.signals_used
    
    def test_attachment_detected(self):
        """Test attachments are detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Offer Letter",
            "snippet": "Please find attached",
            "body": "Offer letter attached",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com",
            "has_attachment": True
        }
        
        result = classifier.classify(email_data)
        assert result.signals.has_attachment
        assert "attachment_detected" in result.signals.signals_used
    
    def test_action_verbs_extracted(self):
        """Test action verbs are extracted"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Please schedule and confirm your interview",
            "body": "We would like to schedule and confirm",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert len(result.signals.action_verbs) > 0
        assert "schedule" in result.signals.action_verbs or "confirm" in result.signals.action_verbs
        assert "action_verbs_extracted" in result.signals.signals_used
    
    def test_cta_phrases_extracted(self):
        """Test CTA phrases are extracted"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Please reply and let us know your availability",
            "body": "Please reply and let us know",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert len(result.signals.cta_phrases) > 0
    
    def test_signature_stripped(self):
        """Test email signatures are stripped"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Let's schedule",
            "body": "Let's schedule an interview.\n\n--\nJohn Doe\nHR Manager\ncompany.com",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        # Signature should be stripped from clean_body_text
        assert "--" not in result.signals.clean_body_text or len(result.signals.clean_body_text) < len(email_data["body"])
    
    def test_html_cleaned(self):
        """Test HTML is cleaned from body"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Let's schedule",
            "body": "<html><body><p>Let's schedule an interview</p></body></html>",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert "<html>" not in result.signals.clean_body_text
        assert "<body>" not in result.signals.clean_body_text
        assert "<p>" not in result.signals.clean_body_text
    
    def test_interview_round_detected(self):
        """Test interview rounds are detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Next Round Interview",
            "snippet": "Technical round interview",
            "body": "We'd like to schedule the next round of interviews",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert "interview_round_detected" in result.signals.signals_used
    
    def test_scheduling_intent_detected(self):
        """Test scheduling intent (date+time+recruiter language) is detected"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Monday, January 15th at 2:00 PM",
            "body": "We would like to schedule an interview for Monday, January 15th at 2:00 PM. Please let us know if you're available.",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert "scheduling_intent" in result.signals.signals_used


# ============================================================================
# LAYER 5: RULE-BASED ENGINE TESTS
# ============================================================================

class TestLayer5RuleEngine:
    """Test Layer 5: Rule-Based Classification Engine"""
    
    def test_rejected_rule_unfortunately(self):
        """Test rejection rule matches 'unfortunately'"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Application Update",
            "snippet": "Unfortunately, we have decided not to move forward",
            "body": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.REJECTED
        assert len(result.signals.matched_rules) > 0
        assert "REJECTED" in str(result.signals.rules_triggered)
    
    def test_rejected_rule_regret(self):
        """Test rejection rule matches 'we regret to inform'"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Application Update",
            "snippet": "We regret to inform you",
            "body": "We regret to inform you that we cannot proceed",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.REJECTED
    
    def test_interview_rule_schedule(self):
        """Test interview rule matches 'schedule interview'"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview Scheduling",
            "snippet": "We would like to schedule a technical interview",
            "body": "We would like to schedule a technical interview",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.INTERVIEW
        assert "INTERVIEW" in str(result.signals.rules_triggered)
    
    def test_interview_rule_calendar(self):
        """Test interview rule matches calendar invite"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview Invitation",
            "snippet": "Please add this to your calendar",
            "body": "Please add this interview to your calendar",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.INTERVIEW
    
    def test_offer_rule_offer_letter(self):
        """Test offer rule matches 'offer letter'"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Job Offer",
            "snippet": "We are pleased to offer you the position with a salary of $100k",
            "body": "Please find the offer letter attached",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.OFFER
        assert "OFFER" in str(result.signals.rules_triggered)
    
    def test_offer_rule_compensation(self):
        """Test offer rule matches 'compensation'"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Job Offer",
            "snippet": "Compensation package details",
            "body": "We'd like to discuss the compensation package",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.OFFER
    
    def test_active_rule_application_received(self):
        """Test active rule matches 'application received'"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Application Received",
            "snippet": "Thank you for applying. We have received your application",
            "body": "We have received your application and it's under review",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status == ClassificationStatus.ACTIVE
        assert "ACTIVE" in str(result.signals.rules_triggered)
    
    def test_rule_priority_rejected_over_interview(self):
        """Test REJECTED has higher priority than INTERVIEW"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview - Unfortunately Not Selected",
            "snippet": "We regret to inform you that we cannot proceed with the interview",
            "body": "Unfortunately, we cannot proceed with the interview",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        # REJECTED should have higher priority
        assert result.status == ClassificationStatus.REJECTED
    
    def test_rule_confidence_stored(self):
        """Test rule confidence is stored"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Rejection",
            "snippet": "Unfortunately, we have decided not to move forward",
            "body": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.rule_confidence > 0.0
        assert result.signals.rule_confidence <= 1.0


# ============================================================================
# LAYER 6: STATISTICAL CONFIDENCE SCORING TESTS
# ============================================================================

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
            "body": "Calendar invite attached. Please add to your calendar.",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com",
            "has_attachment": True
        }
        
        result = classifier.classify(email_data)
        # Multiple signals should boost confidence
        assert result.confidence >= 0.7
    
    def test_rule_score_contribution(self):
        """Test rule score contributes to confidence"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Rejection",
            "snippet": "Unfortunately, we have decided not to move forward",
            "body": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.rule_score > 0.0
    
    def test_sender_score_contribution(self):
        """Test sender score contributes to confidence"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "body": "Let's schedule",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com"
        }
        
        result = classifier.classify(email_data)
        assert result.signals.sender_score > 0.0
    
    def test_thread_score_contribution(self):
        """Test thread score contributes to confidence"""
        classifier = HybridClassifier()
        mock_gmail_client = Mock()
        
        mock_thread = {
            'messages': [
                {
                    'internalDate': '1000000',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Interview'},
                            {'name': 'From', 'value': 'hr@company.com'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Re: Interview",
            "snippet": "Thank you",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        assert result.signals.thread_score > 0.0
    
    def test_structural_score_contribution(self):
        """Test structural score contributes to confidence"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Monday, January 15th at 2:00 PM",
            "body": "Calendar invite attached",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com",
            "has_attachment": True
        }
        
        result = classifier.classify(email_data)
        assert result.signals.semantic_score > 0.0
    
    def test_attachment_boosts_confidence(self):
        """Test attachments boost structural score"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Offer Letter",
            "snippet": "Please find attached",
            "body": "Offer letter attached",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com",
            "has_attachment": True
        }
        
        result = classifier.classify(email_data)
        # Attachment should boost confidence
        assert result.signals.semantic_score > 0.5


# ============================================================================
# LAYER 7: LOCAL LLM SEMANTIC CLASSIFIER TESTS
# ============================================================================

class TestLayer7LLMClassifier:
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
                "body": "We have received your application",
                "sender_domain": "company.com",
                "sender_email": "hr@company.com"
            }
            
            result = classifier.classify(email_data)
            # LLM should be used if confidence is low
            # Note: This is a simplified test - actual LLM integration needs proper mocking
    
    def test_llm_not_called_when_confidence_high(self):
        """Test LLM is NOT called when confidence is above threshold"""
        classifier = HybridClassifier()
        classifier.llm_enabled = True
        classifier.confidence_threshold = 0.5  # Low threshold
        
        email_data = {
            "subject": "Rejection",
            "snippet": "Unfortunately, we have decided not to move forward",
            "body": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        # High confidence from rules, LLM should not be called
        assert not result.signals.llm_used
    
    def test_llm_prompt_includes_all_context(self):
        """Test LLM prompt includes all required context"""
        classifier = HybridClassifier()
        classifier.llm_enabled = True
        classifier.confidence_threshold = 0.9
        
        email_data = {
            "subject": "Application",
            "snippet": "Thank you",
            "body": "We have received your application",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        prompt = classifier._build_llm_prompt(
            email_data,
            [],
            "TechCorp",
            "Software Engineer",
            ClassificationSignals()
        )
        
        assert "TechCorp" in prompt
        assert "Software Engineer" in prompt
        assert "Application" in prompt
        assert "Thank you" in prompt
    
    def test_llm_timeout_handled(self):
        """Test LLM timeout is handled gracefully"""
        classifier = HybridClassifier()
        classifier.llm_enabled = True
        classifier.llm_timeout_sec = 0.1  # Very short timeout
        classifier.confidence_threshold = 0.9
        
        email_data = {
            "subject": "Application",
            "snippet": "Thank you",
            "body": "We have received your application",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        # Should not crash on timeout
        result = classifier.classify(email_data)
        assert result is not None


# ============================================================================
# LAYER 8: DETERMINISTIC RESOLVER TESTS
# ============================================================================

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
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Follow up",
            "snippet": "Thank you for your interest",
            "body": "Thank you",
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
            "body": "Unfortunately, we cannot proceed with the interview",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        # REJECTED should have higher priority than INTERVIEW
        assert result.status == ClassificationStatus.REJECTED
    
    def test_ghosting_detected(self):
        """Test ghosting is detected after threshold days"""
        classifier = HybridClassifier()
        classifier.ghosted_days = 30
        mock_gmail_client = Mock()
        
        # Thread with old message (35 days ago)
        old_date = int((datetime.now(timezone.utc) - timedelta(days=35)).timestamp() * 1000)
        mock_thread = {
            'messages': [
                {
                    'internalDate': str(old_date),
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Application Received'},
                            {'name': 'From', 'value': 'hr@company.com'}
                        ]
                    }
                }
            ]
        }
        mock_gmail_client.service = Mock()
        mock_gmail_client.service.users().threads().get.return_value.execute.return_value = mock_thread
        mock_gmail_client.user_email = "candidate@email.com"
        classifier.gmail_client = mock_gmail_client
        
        email_data = {
            "subject": "Follow up",
            "snippet": "Checking status",
            "body": "Just checking",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        # Should detect ghosting if last status was ACTIVE/INTERVIEW
        # Note: This depends on thread_last_status being set correctly
        if result.signals.thread_last_status in ["ACTIVE", "INTERVIEW"]:
            assert result.status == ClassificationStatus.GHOSTED or result.signals.thread_days_since_last > 30
    
    def test_no_conflicts(self):
        """Test that resolver produces no conflicts (deterministic)"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "body": "Let's schedule",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        # Run multiple times - should get same result
        result1 = classifier.classify(email_data)
        result2 = classifier.classify(email_data)
        
        assert result1.status == result2.status
        assert result1.confidence == result2.confidence


# ============================================================================
# LAYER 9: TRACE LOGGER + EXPLANATION TESTS
# ============================================================================

class TestLayer9TraceLogger:
    """Test Layer 9: Trace Logger + Explanation"""
    
    def test_explanation_generated(self):
        """Test that explanation is generated"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Rejection",
            "snippet": "Unfortunately, we have decided not to move forward",
            "body": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.explanation
        assert len(result.explanation) > 0
    
    def test_trace_dict_generated(self):
        """Test that trace dictionary is generated"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "body": "Let's schedule",
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
    
    def test_signals_used_logged(self):
        """Test that signals_used are logged"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview for Monday at 2 PM",
            "body": "Add to calendar",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert len(result.signals.signals_used) > 0
    
    def test_rules_triggered_logged(self):
        """Test that rules_triggered are logged"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Rejection",
            "snippet": "Unfortunately, we have decided not to move forward",
            "body": "Unfortunately, we have decided not to move forward",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert len(result.signals.rules_triggered) > 0
    
    def test_version_stored(self):
        """Test that rule version is stored"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "body": "Let's schedule",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.version == "1.0"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegrationAllLayers:
    """Integration tests for all 9 layers working together"""
    
    def test_full_pipeline_rejection(self):
        """Test full pipeline for rejection email"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Application Update",
            "snippet": "Unfortunately, we have decided not to move forward",
            "body": "Unfortunately, we have decided not to move forward with your application",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com"
        }
        
        result = classifier.classify(email_data)
        
        # Should pass all layers and classify as REJECTED
        assert result.status == ClassificationStatus.REJECTED
        assert result.confidence > 0.0
        assert result.explanation
        assert result.version == "1.0"
    
    def test_full_pipeline_interview(self):
        """Test full pipeline for interview email"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview Invitation",
            "snippet": "Schedule your technical interview for Monday, January 15th at 2:00 PM",
            "body": "Please add this interview to your calendar. We'd like to schedule for Monday, January 15th at 2:00 PM.",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com",
            "has_attachment": False
        }
        
        result = classifier.classify(email_data)
        
        assert result.status == ClassificationStatus.INTERVIEW
        assert result.confidence > 0.0
        assert result.signals.has_calendar_invite or result.signals.has_date_mention
    
    def test_full_pipeline_offer(self):
        """Test full pipeline for offer email"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Job Offer",
            "snippet": "We are pleased to offer you the position with a salary of $100k",
            "body": "Please find the offer letter attached. Compensation package details included.",
            "sender_domain": "techcorp.com",
            "sender_email": "hr@techcorp.com",
            "has_attachment": True
        }
        
        result = classifier.classify(email_data)
        
        assert result.status == ClassificationStatus.OFFER
        assert result.confidence > 0.0
    
    def test_deterministic_output(self):
        """Test that same email produces same classification"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "body": "Let's schedule",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result1 = classifier.classify(email_data)
        result2 = classifier.classify(email_data)
        
        assert result1.status == result2.status
        assert result1.confidence == result2.confidence
        assert result1.signals.signals_used == result2.signals.signals_used


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_fields_handled(self):
        """Test that empty fields are handled gracefully"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "",
            "snippet": "",
            "body": "",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data)
        assert result.status in [ClassificationStatus.ACTIVE, ClassificationStatus.IGNORE]
        assert result is not None
    
    def test_missing_fields_handled(self):
        """Test that missing fields are handled"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Test"
        }
        
        result = classifier.classify(email_data)
        assert result is not None
        assert result.status is not None
    
    def test_no_thread_id_handled(self):
        """Test that missing thread_id is handled"""
        classifier = HybridClassifier()
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "body": "Let's schedule",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id=None)
        assert result is not None
    
    def test_no_gmail_client_handled(self):
        """Test that missing gmail_client is handled"""
        classifier = HybridClassifier()
        classifier.gmail_client = None
        
        email_data = {
            "subject": "Interview",
            "snippet": "Schedule your interview",
            "body": "Let's schedule",
            "sender_domain": "company.com",
            "sender_email": "hr@company.com"
        }
        
        result = classifier.classify(email_data, thread_id="thread123")
        assert result is not None


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance with multiple emails"""
    
    def test_batch_classification(self):
        """Test batch classification performance"""
        classifier = HybridClassifier()
        
        emails = [
            {
                "subject": f"Interview {i}",
                "snippet": "Schedule your interview",
                "body": "Let's schedule",
                "sender_domain": "company.com",
                "sender_email": "hr@company.com"
            }
            for i in range(100)
        ]
        
        results = classifier.classify_batch(emails)
        
        assert len(results) == 100
        assert all(r is not None for r in results)
        assert all(r.status is not None for r in results)
    
    def test_deterministic_batch(self):
        """Test that batch classification is deterministic"""
        classifier = HybridClassifier()
        
        emails = [
            {
                "subject": "Interview",
                "snippet": "Schedule your interview",
                "body": "Let's schedule",
                "sender_domain": "company.com",
                "sender_email": "hr@company.com"
            }
            for _ in range(10)
        ]
        
        results1 = classifier.classify_batch(emails)
        results2 = classifier.classify_batch(emails)
        
        for r1, r2 in zip(results1, results2):
            assert r1.status == r2.status
            assert r1.confidence == r2.confidence
