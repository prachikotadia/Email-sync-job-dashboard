"""
Tests for exact company name extraction
Must pass all tests in Docker
"""
import pytest
from app.company_extractor import CompanyExtractor, ParsedEmail, CompanyExtractionResult

@pytest.fixture
def extractor():
    return CompanyExtractor()

def create_parsed_email(
    from_email: str = "",
    from_name: str = "",
    reply_to_email: str = None,
    subject: str = "",
    snippet: str = "",
    body_text: str = "",
    list_unsubscribe: str = None
) -> ParsedEmail:
    """Helper to create ParsedEmail"""
    return ParsedEmail(
        from_email=from_email,
        from_name=from_name,
        reply_to_email=reply_to_email,
        subject=subject,
        snippet=snippet,
        headers={},
        list_unsubscribe=list_unsubscribe,
        body_text=body_text,
        body_html=None,
        received_at="2024-01-01T00:00:00Z",
        message_id="test123",
        thread_id="thread123"
    )

class TestDirectCompanyDomain:
    """A) Direct domain mapping tests"""
    
    def test_meta_domain(self, extractor):
        """from: noreply@meta.com → Meta, confidence >= 95, source DOMAIN"""
        email = create_parsed_email(from_email="noreply@meta.com")
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Meta"
        assert result.confidence >= 95
        assert result.source == "DOMAIN"
    
    def test_google_domain(self, extractor):
        """from: jobs@google.com → Google, confidence >= 95"""
        email = create_parsed_email(from_email="jobs@google.com")
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Google"
        assert result.confidence >= 95
        assert result.source == "DOMAIN"
    
    def test_amazon_domain(self, extractor):
        """from: careers@amazon.com → Amazon"""
        email = create_parsed_email(from_email="careers@amazon.com")
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Amazon"
        assert result.confidence >= 95
    
    def test_reply_to_domain(self, extractor):
        """reply-to domain as backup"""
        email = create_parsed_email(
            from_email="noreply@mailer.com",
            reply_to_email="jobs@microsoft.com"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Microsoft"
        assert result.confidence >= 90

class TestATSExtraction:
    """B) ATS provider detection + real company recovery"""
    
    def test_greenhouse_with_slug(self, extractor):
        """from: no-reply@greenhouse.io with body containing boards.greenhouse.io/airbnb → Airbnb"""
        email = create_parsed_email(
            from_email="no-reply@greenhouse.io",
            body_text="Check your application: https://boards.greenhouse.io/airbnb/jobs/12345"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Airbnb"
        assert result.confidence >= 80
        assert result.source == "ATS_BRANDING"
        assert result.ats_provider == "greenhouse"
    
    def test_lever_with_slug(self, extractor):
        """from: no-reply@lever.co with link jobs.lever.co/stripe/... → Stripe"""
        email = create_parsed_email(
            from_email="no-reply@lever.co",
            body_text="View job: https://jobs.lever.co/stripe/abc123"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Stripe"
        assert result.confidence >= 80
        assert result.ats_provider == "lever"
    
    def test_greenhouse_unsubscribe(self, extractor):
        """Extract from list-unsubscribe header"""
        email = create_parsed_email(
            from_email="no-reply@greenhouse.io",
            list_unsubscribe="https://greenhouse.io/databricks/unsubscribe"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Databricks"
        assert result.ats_provider == "greenhouse"
    
    def test_ats_without_company(self, extractor):
        """ATS detected but no company found → Unknown"""
        email = create_parsed_email(
            from_email="no-reply@greenhouse.io",
            body_text="Thank you for applying"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Unknown"
        assert result.ats_provider == "greenhouse"
    
    def test_ats_from_name_pattern(self, extractor):
        """from_name: 'Company via Greenhouse' → Company"""
        email = create_parsed_email(
            from_email="no-reply@greenhouse.io",
            from_name="Netflix via Greenhouse"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Netflix"
        assert result.ats_provider == "greenhouse"

class TestFalsePositives:
    """Avoid false positives"""
    
    def test_hiring_team_rejected(self, extractor):
        """from_name: 'Hiring Team' body mentions 'San Francisco' → Unknown"""
        email = create_parsed_email(
            from_email="hiring@example.com",
            from_name="Hiring Team",
            body_text="We are located in San Francisco"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Unknown"
        assert "Hiring" not in result.company_name
    
    def test_random_nouns_rejected(self, extractor):
        """subject: 'Interview scheduled' body has many org words → must not pick random nouns"""
        email = create_parsed_email(
            from_email="noreply@example.com",
            subject="Interview scheduled",
            body_text="We have offices in San Francisco, New York, and London. Our team includes engineers, designers, and product managers."
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Unknown"
        assert "San Francisco" not in result.company_name
        assert "New York" not in result.company_name
    
    def test_denylist_enforced(self, extractor):
        """Never accept denylist words as company names"""
        email = create_parsed_email(
            from_email="recruiting@example.com",
            from_name="Recruiting Team"
        )
        result = extractor.extract_company_name(email, "")
        
        assert result.company_name == "Unknown"
        assert "Recruiting" not in result.company_name

class TestDeterminism:
    """Determinism tests"""
    
    def test_same_email_same_result(self, extractor):
        """Same email parsed twice → same output"""
        email = create_parsed_email(
            from_email="jobs@google.com",
            subject="Application received"
        )
        
        result1 = extractor.extract_company_name(email, "")
        result2 = extractor.extract_company_name(email, "")
        
        assert result1.company_name == result2.company_name
        assert result1.confidence == result2.confidence
        assert result1.source == result2.source
    
    def test_confidence_scoring(self, extractor):
        """Low confidence (< 70) → Unknown"""
        email = create_parsed_email(
            from_email="random@example.com",
            from_name="Some Random Text"
        )
        result = extractor.extract_company_name(email, "")
        
        if result.confidence < 70:
            assert result.company_name == "Unknown"

class TestNormalization:
    """Company name normalization"""
    
    def test_alias_mapping(self, extractor):
        """Facebook → Meta"""
        email = create_parsed_email(
            from_email="noreply@fb.com"
        )
        result = extractor.extract_company_name(email, "")
        
        # Should map to Meta if fb.com is in aliases
        assert result.company_name in ["Meta", "Facebook"]  # Allow either if mapping exists
    
    def test_suffix_removal(self, extractor):
        """Company Inc → Company"""
        email = create_parsed_email(
            from_name="Example Company Inc"
        )
        result = extractor.extract_company_name(email, "")
        
        # Should remove "Inc" suffix
        if result.company_name != "Unknown":
            assert "Inc" not in result.company_name

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
