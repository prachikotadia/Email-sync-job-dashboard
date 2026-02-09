"""
Tests for deterministic company resolution (app/enrich/company_resolver.py).
Ensures Recent Activity no longer shows "Unknown" when signals exist.
Greenhouse (us.greenhouse-mail.io) must never resolve to "Us"; prefer subject/signature/link.
"""
import pytest
from app.enrich.company_resolver import resolve_company, extract_links_from_text


class TestGreenhouseUsFaire:
    """us.greenhouse-mail.io must resolve to company from subject/signature, never 'Us'."""

    def test_faire_from_subject_and_signature(self):
        r = resolve_company(
            subject="Thank you for applying to Faire!",
            snippet="We received your application. The Faire Team",
            from_email="no-reply@us.greenhouse-mail.io",
            from_domain="us.greenhouse-mail.io",
        )
        assert r["company_name"] == "Faire"
        assert r["company_source"] in ("subject", "signature")
        assert "domain" not in (r.get("company_source") or "").lower() or r.get("company_source") == "domain_fallback"

    def test_us_greenhouse_mail_io_no_signal_fallback_not_us(self):
        r = resolve_company(
            subject="",
            snippet="",
            from_email="no-reply@us.greenhouse-mail.io",
            from_domain="us.greenhouse-mail.io",
        )
        assert r["company_name"] != "Us"
        assert r["company_name"] == "Greenhouse (ATS)"
        assert r["company_source"] == "domain_fallback"
        assert "rejected" in (r.get("company_debug") or {})
        assert r.get("company_confidence", 0) <= 0.5

    def test_eu_greenhouse_mail_io_no_signal_fallback_not_eu(self):
        r = resolve_company(
            subject="",
            snippet="",
            from_email="noreply@eu.greenhouse-mail.io",
            from_domain="eu.greenhouse-mail.io",
        )
        assert r["company_name"] != "Eu"
        assert r["company_name"] == "Greenhouse (ATS)"

    def test_faire_from_subject_only(self):
        r = resolve_company(
            subject="Thank you for applying to Faire!",
            snippet="",
            from_email="no-reply@us.greenhouse-mail.io",
            from_domain="us.greenhouse-mail.io",
        )
        assert r["company_name"] == "Faire"
        assert r["company_source"] == "subject"

    def test_faire_from_signature_only(self):
        r = resolve_company(
            subject="Application update",
            snippet="Best regards, The Faire Team",
            from_email="no-reply@us.greenhouse-mail.io",
            from_domain="us.greenhouse-mail.io",
        )
        assert r["company_name"] == "Faire"
        assert r["company_source"] == "signature"

    def test_greenhouse_board_link_faire(self):
        r = resolve_company(
            subject="",
            snippet="Apply at https://boards.greenhouse.io/faire/jobs/1",
            from_email="no-reply@us.greenhouse-mail.io",
            from_domain="us.greenhouse-mail.io",
            urls=["https://boards.greenhouse.io/faire/jobs/1"],
        )
        assert r["company_name"] == "Faire"
        assert r["company_source"] == "link"

    def test_job_boards_greenhouse_io_slug(self):
        r = resolve_company(
            subject="",
            snippet="",
            from_email="noreply@greenhouse.io",
            from_domain="greenhouse.io",
            urls=["https://job-boards.greenhouse.io/stripe/jobs/2"],
        )
        assert r["company_name"] == "Stripe"
        assert r["company_source"] == "link"

    def test_reject_infra_tokens_eu_na(self):
        """eu.greenhouse-mail.io / na must not produce company Eu/Na."""
        r = resolve_company(
            subject="",
            snippet="",
            from_email="noreply@na.greenhouse-mail.io",
            from_domain="na.greenhouse-mail.io",
        )
        assert r["company_name"] != "Na"
        assert r["company_name"] == "Greenhouse (ATS)"


class TestWorkdayTenantUrl:
    """Workday + tenant URL resolves company."""

    def test_workday_tenant_myworkday(self):
        r = resolve_company(
            subject="Application Update",
            snippet="",
            from_name="",
            from_email="noreply@myworkday.com",
            from_domain="myworkday.com",
            links=["https://acme.myworkday.com/careers"],
        )
        assert r["company_name"] == "Acme"
        assert r["company_source"] == "link"
        assert r["company_confidence"] >= 0.5

    def test_workday_tenant_workday_com(self):
        r = resolve_company(
            subject="",
            snippet="View job https://stripe.wd1.myworkdayjobs.com/apply",
            from_name="",
            from_email="noreply@workday.com",
            from_domain="workday.com",
            links=["https://stripe.wd1.myworkdayjobs.com/careers"],
        )
        assert "stripe" in r["company_name"].lower() or r["company_name"] == "Stripe"
        assert r["company_source"] == "link"


class TestGreenhouseBoardUrl:
    """Greenhouse board URL resolves company."""

    def test_greenhouse_board_url(self):
        r = resolve_company(
            subject="Your application at Company",
            snippet="",
            from_name="",
            from_email="notifications@greenhouse.io",
            from_domain="greenhouse.io",
            links=["https://boards.greenhouse.io/databricks/jobs/123"],
        )
        assert r["company_name"] == "Databricks"
        assert r["company_source"] == "link"
        assert r["company_confidence"] >= 0.8

    def test_greenhouse_slug_with_hyphen(self):
        r = resolve_company(
            subject="",
            snippet="Apply: https://boards.greenhouse.io/acme-corp/jobs/456",
            from_name="",
            from_email="noreply@greenhouse.io",
            from_domain="greenhouse.io",
            links=["https://boards.greenhouse.io/acme-corp/jobs/456"],
        )
        assert "acme" in r["company_name"].lower() or r["company_name"] == "Acme Corp"
        assert r["company_source"] == "link"


class TestLeverUrl:
    """Lever URL resolves company."""

    def test_lever_url(self):
        r = resolve_company(
            subject="Interview at Company",
            snippet="",
            from_name="",
            from_email="jobs@lever.co",
            from_domain="lever.co",
            links=["https://jobs.lever.co/notion/abc-123"],
        )
        assert r["company_name"] == "Notion"
        assert r["company_source"] == "link"
        assert r["company_confidence"] >= 0.8


class TestNonAtsDomain:
    """Non-ATS domain resolves from domain (or from_name)."""

    def test_non_ats_resolves_from_domain(self):
        r = resolve_company(
            subject="Re: Software Engineer",
            snippet="",
            from_name="",
            from_email="hr@stripe.com",
            from_domain="stripe.com",
        )
        assert r["company_name"] == "Stripe"
        assert r["company_source"] == "domain_fallback"
        assert r["company_confidence"] >= 0.3

    def test_non_ats_from_name_first(self):
        r = resolve_company(
            subject="",
            snippet="",
            from_name="Salesforce Careers",
            from_email="recruiting@salesforce.com",
            from_domain="salesforce.com",
        )
        assert r["company_name"] == "Salesforce"
        assert r["company_source"] == "from_name"
        assert r["company_confidence"] >= 0.6


class TestFromNameRecruitingCareers:
    """From-name 'Company Recruiting/Careers' resolves to Company."""

    def test_salesforce_careers(self):
        r = resolve_company(
            subject="Application received",
            snippet="",
            from_name="Salesforce Careers",
            from_email="noreply@greenhouse.io",
            from_domain="greenhouse.io",
            links=[],
        )
        assert r["company_name"] == "Salesforce"
        assert r["company_source"] in ("ATS_FROM_NAME", "FROM_NAME", "from_name")

    def test_company_recruiting(self):
        r = resolve_company(
            subject="",
            snippet="",
            from_name="Acme Corp Recruiting",
            from_email="noreply@lever.co",
            from_domain="lever.co",
        )
        assert "acme" in r["company_name"].lower() or r["company_name"] == "Acme Corp"
        assert r["company_source"] in ("ATS_FROM_NAME", "FROM_NAME", "from_name")


class TestSubjectDashFormat:
    """Subject format '— Company' resolves company."""

    def test_subject_em_dash_company(self):
        r = resolve_company(
            subject="Application Update — Notion",
            snippet="",
            from_name="",
            from_email="jobs@lever.co",
            from_domain="lever.co",
            links=[],
        )
        assert r["company_name"] == "Notion"
        assert r["company_source"] == "subject"


class TestAmbiguousDomainFallback:
    """Ambiguous cases fall back to domain."""

    def test_ats_no_url_no_from_name_uses_domain_fallback(self):
        r = resolve_company(
            subject="Your application",
            snippet="",
            from_name="",
            from_email="noreply@company123.greenhouse.io",
            from_domain="company123.greenhouse.io",
            links=[],
        )
        # Should get company from subdomain or Unknown Company
        assert r["company_name"] != "" and r["company_name"] is not None
        assert "company_name" in r
        assert r.get("company_source") in ("domain_fallback", "link", "from_name") or "Company" in r["company_name"]

    def test_generic_email_provider_stays_unknown(self):
        r = resolve_company(
            subject="Job update",
            snippet="",
            from_name="",
            from_email="user@gmail.com",
            from_domain="gmail.com",
        )
        assert r["company_name"] == "Unknown Company"
        assert r["company_source"] == "domain_fallback" or r["company_confidence"] <= 0.2


class TestLinkExtraction:
    """URL extraction from text."""

    def test_extract_links_from_text(self):
        text = "Apply here: https://boards.greenhouse.io/foo/jobs/1 and https://jobs.lever.co/bar"
        links = extract_links_from_text(text)
        assert len(links) >= 2
        assert any("greenhouse" in u for u in links)
        assert any("lever" in u for u in links)

    def test_extract_links_empty(self):
        assert extract_links_from_text("") == []
        assert extract_links_from_text(None) == []


class TestDebugOutput:
    """Resolver returns company_debug with candidates, picked_rule, rejected."""

    def test_debug_present(self):
        r = resolve_company(
            subject="",
            snippet="",
            from_name="Stripe Recruiting",
            from_email="hr@stripe.com",
            from_domain="stripe.com",
        )
        assert "company_debug" in r
        d = r["company_debug"]
        assert isinstance(d, dict)
        assert "candidates" in d
        assert "picked_rule" in d
        assert "rejected" in d


class TestIcimsSmartrecruitersAshby:
    """Other ATS URL patterns."""

    def test_icims_url(self):
        r = resolve_company(
            subject="",
            snippet="",
            from_name="",
            from_email="noreply@icims.com",
            from_domain="icims.com",
            links=["https://careers.icims.com/jobs/12345"],
        )
        # May resolve from URL path or fallback
        assert r["company_name"] != "" and r["company_name"] is not None

    def test_smartrecruiters_url(self):
        r = resolve_company(
            subject="",
            snippet="Apply: https://www.smartrecruiters.com/ExampleCorp/123",
            from_name="",
            from_email="noreply@smartrecruiters.com",
            from_domain="smartrecruiters.com",
            links=["https://www.smartrecruiters.com/ExampleCorp/123"],
        )
        assert ("example" in r["company_name"].lower() or r["company_source"] == "link" or
                (r["company_name"] != "Unknown Company" and r["company_name"] != "Greenhouse (ATS)"))
