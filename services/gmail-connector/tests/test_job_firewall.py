"""
Job Email Firewall tests. Non-negotiable: these exact cases must be deterministic.
Blocked emails must never enter job pipeline; debug endpoint must show exact matched rule IDs.
"""
import pytest
from app.classifiers.job_firewall import firewall, _load_config


def _r(id_: str, type_: str, value: str) -> dict:
    return {"id": id_, "type": type_, "value": value}


class TestBuiltInJobMatches:
    """BuiltIn 'Your New Job Matches' → DENY category NON_JOB_ALERT."""

    def test_builtin_your_new_job_matches_deny_non_job_alert(self):
        result = firewall(
            subject="Your New Job Matches",
            snippet="We found new roles that match your profile. Unsubscribe here.",
            from_email="alerts@builtin.com",
            from_domain="builtin.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_ALERT"
        assert result["allow"] is False
        assert any(
            r.get("id") == "job_alert_domain" or "job matches" in str(r.get("value", "")).lower() or "builtin" in str(r.get("value", "")).lower()
            for r in result["matched_rules"]
        ), f"Expected matched rule for job alert; got {result['matched_rules']}"


class TestIndeedRecommendations:
    """Indeed 'Discover new opportunities / jobs just dropped' → DENY category NON_JOB_ALERT."""

    def test_indeed_discover_new_opportunities_deny(self):
        result = firewall(
            subject="Discover new opportunities for you",
            snippet="Jobs just dropped that match your preferences.",
            from_email="job-alerts@indeed.com",
            from_domain="indeed.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_ALERT"
        assert result["allow"] is False
        assert any(
            r.get("type") == "deny" for r in result["matched_rules"]
        ), f"Expected deny rule; got {result['matched_rules']}"

    def test_indeed_jobs_just_dropped_deny(self):
        result = firewall(
            subject="Jobs just dropped",
            snippet="Check out these new recommendations.",
            from_email="noreply@indeed.com",
            from_domain="indeed.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_ALERT"
        assert result["allow"] is False


class TestGoogleSecurityAuth:
    """Google 'Security alert / allowed access / verification' → DENY category NON_JOB_AUTH."""

    def test_google_security_alert_deny(self):
        result = firewall(
            subject="Security alert",
            snippet="New sign-in on your Google account. If this was you, no action needed.",
            from_email="no-reply@accounts.google.com",
            from_domain="accounts.google.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_AUTH"
        assert result["allow"] is False
        assert any(
            "domain_deny" in str(r.get("id", "")) or "accounts.google" in str(r.get("value", ""))
            for r in result["matched_rules"]
        ), f"Expected domain or auth rule; got {result['matched_rules']}"

    def test_google_verification_code_deny(self):
        result = firewall(
            subject="Your verification code",
            snippet="One-time password: 123456. Do not share.",
            from_email="noreply@google.com",
            from_domain="google.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_AUTH"
        assert result["allow"] is False

    def test_otp_keyword_deny(self):
        result = firewall(
            subject="Your OTP",
            snippet="Use this code to verify your email.",
            from_email="noreply@example.com",
            from_domain="example.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_AUTH"
        assert result["allow"] is False
        assert any(
            "keyword_deny" in str(r.get("id", "")) for r in result["matched_rules"]
        ), f"Expected keyword deny; got {result['matched_rules']}"


class TestRenderDeploy:
    """Render confirmation/build → DENY category NON_JOB_DEVOPS."""

    def test_render_build_deny(self):
        result = firewall(
            subject="Your deployment succeeded",
            snippet="Build succeeded. Your site is live.",
            from_email="deploy@render.com",
            from_domain="render.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_DEVOPS"
        assert result["allow"] is False
        assert any(
            "render" in str(r.get("value", "")).lower() for r in result["matched_rules"]
        ), f"Expected domain deny for render; got {result['matched_rules']}"

    def test_netlify_deploy_deny(self):
        result = firewall(
            subject="Build failed",
            snippet="Deployment failed for your site.",
            from_email="notifications@netlify.com",
            from_domain="netlify.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_DEVOPS"
        assert result["allow"] is False


class TestUnsubscribePromo:
    """Any email containing 'unsubscribe' → DENY category NON_JOB_PROMO."""

    def test_unsubscribe_deny_promo(self):
        result = firewall(
            subject="Weekly digest",
            snippet="You received this because you subscribed. Unsubscribe here.",
            from_email="news@mailchimp.com",
            from_domain="mailchimp.com",
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_PROMO"
        assert result["allow"] is False
        assert any(
            "unsubscribe" in str(r.get("value", "")).lower() or "mailchimp" in str(r.get("value", "")).lower()
            for r in result["matched_rules"]
        ), f"Expected keyword or domain; got {result['matched_rules']}"


class TestRealRejectionAllow:
    """Real rejection email from workday/greenhouse containing 'not moving forward' → ALLOW (JOB)."""

    def test_workday_rejection_allow(self):
        result = firewall(
            subject="Update on your application",
            snippet="We regret to inform you that we are not moving forward with your application at this time.",
            from_email="noreply@company.wd1.myworkday.com",
            from_domain="company.wd1.myworkday.com",
        )
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert result["allow"] is True
        assert any(
            r.get("type") == "allow" for r in result["matched_rules"]
        ), f"Expected allow rule; got {result['matched_rules']}"

    def test_greenhouse_rejection_allow(self):
        result = firewall(
            subject="Application update",
            snippet="Thank you for your interest. We have decided not to move forward with your application. The position has been filled.",
            from_email="notifications@boards.greenhouse.io",
            from_domain="greenhouse.io",
        )
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert result["allow"] is True


class TestApplicationReceivedAllow:
    """Real application received email 'Thank you for applying' → ALLOW (JOB)."""

    def test_thank_you_for_applying_allow(self):
        result = firewall(
            subject="Application received",
            snippet="Thank you for applying to the Software Engineer role. We have received your application.",
            from_email="careers@company.com",
            from_domain="company.com",
        )
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert result["allow"] is True
        assert any(
            r.get("type") == "allow" for r in result["matched_rules"]
        ), f"Expected allow rule; got {result['matched_rules']}"

    def test_application_submitted_allow(self):
        result = firewall(
            subject="We received your application",
            snippet="Application submitted. Our team will review.",
            from_email="jobs@lever.co",
            from_domain="lever.co",
        )
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert result["allow"] is True


class TestDeterministicAndMatchedRules:
    """Tests must assert deterministic output and matched rule IDs."""

    def test_matched_rules_have_id_type_value(self):
        result = firewall(
            subject="Unsubscribe from our newsletter",
            snippet="Sale! Limited time discount.",
            from_email="marketing@sendgrid.net",
            from_domain="sendgrid.net",
        )
        assert result["decision"] == "DENY"
        for r in result["matched_rules"]:
            assert "id" in r, f"Rule missing id: {r}"
            assert "type" in r, f"Rule missing type: {r}"
            assert "value" in r, f"Rule missing value: {r}"

    def test_same_input_same_output(self):
        r1 = firewall(subject="OTP code", snippet="123456", from_email="noreply@accounts.google.com", from_domain="accounts.google.com")
        r2 = firewall(subject="OTP code", snippet="123456", from_email="noreply@accounts.google.com", from_domain="accounts.google.com")
        assert r1["decision"] == r2["decision"]
        assert r1["category"] == r2["category"]
        assert r1["allow"] == r2["allow"]
        assert [x.get("id") for x in r1["matched_rules"]] == [x.get("id") for x in r2["matched_rules"]]


class TestGmailCategoryPromotions:
    """Gmail category PROMOTIONS → DENY unless strong job signal."""

    def test_gmail_promotions_deny_without_job_signal(self):
        result = firewall(
            subject="Weekly deals",
            snippet="Check out our sale.",
            from_email="promo@store.com",
            from_domain="store.com",
            gmail_label_ids=["CATEGORY_PROMOTIONS", "INBOX"],
        )
        assert result["decision"] == "DENY"
        assert result["category"] == "NON_JOB_PROMO"
        assert result["allow"] is False

    def test_gmail_promotions_allow_with_strong_job_signal(self):
        result = firewall(
            subject="Thank you for applying",
            snippet="We received your application.",
            from_email="hr@company.com",
            from_domain="company.com",
            gmail_label_ids=["CATEGORY_PROMOTIONS", "INBOX"],
        )
        assert result["decision"] == "ALLOW"
        assert result["category"] == "JOB"
        assert result["allow"] is True
