"""
Comprehensive tests for Email Firewall
Tests firewall decision logic with 25+ real-world scenarios
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.classifiers.email_firewall import (
    firewall_decide,
    load_firewall_config,
    normalize_text,
    extract_domain,
    extract_local_part,
    matches_domain_exact,
    matches_domain_substring,
    matches_keywords,
    matches_ats_domain,
    matches_job_keywords,
    matches_sender_pattern,
    matches_strong_job_override
)


class TestEmailFirewall:
    """Test suite for email firewall functionality"""
    
    def test_render_confirmation_deny(self):
        """Test: Render deployment confirmation should be denied"""
        result = firewall_decide(
            subject="Your deployment is live",
            snippet="Your site on Render is now live at https://example.onrender.com",
            from_email="noreply@render.com",
            from_domain="render.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert "render.com" in str(result["matched_rules"]).lower()
        assert result["category"] in ["NON_JOB_DEPLOY", "UNKNOWN"]
    
    def test_netlify_deploy_deny(self):
        """Test: Netlify deployment notification should be denied"""
        result = firewall_decide(
            subject="Deployment successful",
            snippet="Your site has been deployed successfully on Netlify",
            from_email="deploy@netlify.com",
            from_domain="netlify.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert "netlify" in str(result["matched_rules"]).lower()
    
    def test_google_security_alert_deny(self):
        """Test: Google security alert should be denied"""
        result = firewall_decide(
            subject="Security alert: New sign-in",
            snippet="We noticed a new sign-in to your Google account",
            from_email="no-reply@accounts.google.com",
            from_domain="accounts.google.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_AUTH"
        assert any("google" in rule.lower() or "security" in rule.lower() or "sign-in" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_otp_email_deny(self):
        """Test: OTP/verification code email should be denied"""
        result = firewall_decide(
            subject="Your verification code is 123456",
            snippet="Your one-time password (OTP) is 123456. Do not share this code.",
            from_email="noreply@example.com",
            from_domain="example.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_AUTH"
        assert any("otp" in rule.lower() or "verification" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_verify_email_deny(self):
        """Test: Email verification request should be denied"""
        result = firewall_decide(
            subject="Verify your email address",
            snippet="Please confirm your email by clicking the link below",
            from_email="noreply@example.com",
            from_domain="example.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert any("verify" in rule.lower() or "confirm" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_newsletter_unsubscribe_deny(self):
        """Test: Newsletter with unsubscribe should be denied"""
        result = firewall_decide(
            subject="Weekly Newsletter - Special Offers",
            snippet="Check out our latest deals! Unsubscribe here if you no longer want to receive these emails.",
            from_email="newsletter@marketing.com",
            from_domain="marketing.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_PROMO"
        assert any("newsletter" in rule.lower() or "unsubscribe" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_stripe_receipt_deny(self):
        """Test: Stripe payment receipt should be denied"""
        result = firewall_decide(
            subject="Receipt for your payment",
            snippet="Thank you for your payment. Your receipt is attached.",
            from_email="receipts@stripe.com",
            from_domain="stripe.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_BILLING"
        assert any("stripe" in rule.lower() or "receipt" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_zendesk_ticket_deny(self):
        """Test: Zendesk support ticket update should be denied"""
        result = firewall_decide(
            subject="Ticket #12345: Your support request",
            snippet="We received your support request and will respond shortly.",
            from_email="support@zendesk.com",
            from_domain="zendesk.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_SUPPORT"
        assert any("zendesk" in rule.lower() or "ticket" in rule.lower() or "support" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_github_notification_deny(self):
        """Test: GitHub notification should be denied"""
        result = firewall_decide(
            subject="[GitHub] New comment on issue",
            snippet="Someone commented on your issue. View it on GitHub.",
            from_email="notifications@github.com",
            from_domain="github.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert any("github" in rule.lower() for rule in result["matched_rules"])
    
    def test_real_job_application_allow(self):
        """Test: Real job application received email should be allowed"""
        result = firewall_decide(
            subject="Thank you for your application",
            snippet="We received your application for the Software Engineer position. We will review it and get back to you soon.",
            from_email="recruiting@techcompany.com",
            from_domain="techcompany.com"
        )
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert any("application" in rule.lower() or "job_keyword" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_workday_rejection_allow(self):
        """Test: Workday rejection email should be allowed (ATS domain + job terms)"""
        result = firewall_decide(
            subject="Update on your application",
            snippet="We regret to inform you regarding your application for the Software Engineer position. After careful consideration, we have decided to move forward with other candidates.",
            from_email="noreply@workday.com",
            from_domain="workday.com"
        )
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert any("workday" in rule.lower() or "ats_domain" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_interview_scheduling_greenhouse_allow(self):
        """Test: Interview scheduling from Greenhouse should be allowed"""
        result = firewall_decide(
            subject="Interview scheduling - Software Engineer",
            snippet="We would like to schedule an interview with you for the Software Engineer position. Please select a time that works for you.",
            from_email="noreply@greenhouse.io",
            from_domain="greenhouse.io"
        )
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert any("greenhouse" in rule.lower() or "ats_domain" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_ambiguous_no_allow_signals_deny(self):
        """Test: Ambiguous email with no allow signals should be denied by default"""
        result = firewall_decide(
            subject="Meeting reminder",
            snippet="Don't forget about our meeting tomorrow at 2 PM.",
            from_email="colleague@company.com",
            from_domain="company.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "UNKNOWN"
        assert "No allow signals found" in result["reason"]
    
    def test_password_reset_deny(self):
        """Test: Password reset email should be denied"""
        result = firewall_decide(
            subject="Reset your password",
            snippet="Click here to reset your password. This link will expire in 1 hour.",
            from_email="security@example.com",
            from_domain="example.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_AUTH"
        assert any("password" in rule.lower() or "reset" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_invoice_billing_deny(self):
        """Test: Invoice/billing email should be denied"""
        result = firewall_decide(
            subject="Invoice #12345",
            snippet="Your invoice for $99.99 is ready. Payment is due within 30 days.",
            from_email="billing@service.com",
            from_domain="billing.service.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_BILLING"
        assert any("invoice" in rule.lower() or "billing" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_deployment_notification_deny(self):
        """Test: Deployment/build notification should be denied"""
        result = firewall_decide(
            subject="Build succeeded",
            snippet="Your deployment to production was successful. Build #123 completed in 2 minutes.",
            from_email="ci@example.com",
            from_domain="ci.example.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_DEPLOY"
        assert any("deploy" in rule.lower() or "build" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_promo_email_deny(self):
        """Test: Promotional email should be denied"""
        result = firewall_decide(
            subject="Limited time offer - 50% off!",
            snippet="Don't miss out on our special promotion. Get 50% off all products this week only!",
            from_email="promo@store.com",
            from_domain="store.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_PROMO"
        assert any("promo" in rule.lower() or "sale" in rule.lower() or "discount" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_strong_job_override_allows(self):
        """Test: Strong job override phrase should allow even if deny rules match"""
        result = firewall_decide(
            subject="We regret to inform you regarding your application",
            snippet="We regret to inform you regarding your application for the Software Engineer position. After careful review, we have decided not to move forward.",
            from_email="noreply@example.com",
            from_domain="example.com"
        )
        # Should be allowed due to strong job override phrase
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert any("strong_job_override" in rule.lower() for rule in result["matched_rules"])
    
    def test_ats_domain_allow(self):
        """Test: Email from ATS domain should be allowed"""
        result = firewall_decide(
            subject="Application update",
            snippet="Your application status has been updated.",
            from_email="noreply@lever.co",
            from_domain="lever.co"
        )
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert any("lever" in rule.lower() or "ats_domain" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_sender_pattern_allow(self):
        """Test: Email from recruiting@ should be allowed"""
        result = firewall_decide(
            subject="Next steps in your application",
            snippet="We would like to move forward with your application. Please reply to schedule an interview.",
            from_email="recruiting@company.com",
            from_domain="company.com"
        )
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert any("recruiting" in rule.lower() or "sender_pattern" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_job_keyword_allow(self):
        """Test: Email with strong job keywords should be allowed"""
        result = firewall_decide(
            subject="Interview invitation - Software Engineer role",
            snippet="We are pleased to invite you for an interview for the Software Engineer position. Please select a time slot.",
            from_email="hr@company.com",
            from_domain="company.com"
        )
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert any("interview" in rule.lower() or "job_keyword" in rule.lower() 
                   for rule in result["matched_rules"])
    
    def test_subdomain_deny(self):
        """Test: Subdomain of deny domain should be denied"""
        result = firewall_decide(
            subject="Deployment notification",
            snippet="Your site has been deployed.",
            from_email="noreply@api.render.com",
            from_domain="api.render.com"
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
        assert any("render" in rule.lower() for rule in result["matched_rules"])
    
    def test_subdomain_allow(self):
        """Test: Subdomain of ATS domain should be allowed"""
        result = firewall_decide(
            subject="Application received",
            snippet="We received your application and will review it soon.",
            from_email="noreply@api.greenhouse.io",
            from_domain="api.greenhouse.io"
        )
        assert result["allow_job_pipeline"] == True
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
    
    def test_empty_inputs(self):
        """Test: Empty inputs should default to DENY (conservative)"""
        result = firewall_decide(
            subject="",
            snippet="",
            from_email="",
            from_domain=""
        )
        assert result["allow_job_pipeline"] == False
        assert result["decision"] == "DENY"
    
    def test_normalize_text(self):
        """Test: Text normalization works correctly"""
        assert normalize_text("  HELLO   WORLD  ") == "hello world"
        assert normalize_text("") == ""
        assert normalize_text("Test\n\nMultiple\nLines") == "test multiple lines"
    
    def test_extract_domain(self):
        """Test: Domain extraction works correctly"""
        assert extract_domain("user@example.com") == "example.com"
        assert extract_domain("test@sub.domain.com") == "sub.domain.com"
        assert extract_domain("invalid") == ""
        assert extract_domain("") == ""
    
    def test_extract_local_part(self):
        """Test: Local part extraction works correctly"""
        assert extract_local_part("recruiting@company.com") == "recruiting"
        assert extract_local_part("user.name@example.com") == "user.name"
        assert extract_local_part("invalid") == ""
        assert extract_local_part("") == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
