"""
LLM Prompt Template for Email Classification

This template is used by Layer 7 (Local LLM Semantic Classifier) of the
9-layer hybrid classification engine.

WHY THIS PROMPT:
- Includes all relevant context (subject, body, thread, company, role)
- Provides structural signals to help LLM make informed decisions
- Strict JSON output format ensures parseable results
- Low temperature (0.1) for consistent, deterministic output
- No full email body in prompt (privacy-safe, only first 500 chars)
"""

def build_classification_prompt(
    subject: str,
    snippet: str,
    body: str,
    sender_domain: str,
    sender_type: str,
    company_name: Optional[str],
    role: Optional[str],
    thread_summary: str,
    has_calendar: bool,
    has_date: bool,
    has_time: bool
) -> str:
    """
    Build LLM prompt for email classification.
    
    WHY THIS STRUCTURE:
    - Categories listed first for clarity
    - Email data provided in structured format
    - Context (company, role, thread) helps LLM understand job application context
    - Structural signals (calendar, dates) help identify interview scheduling
    - Strict JSON format ensures parseable output
    - No full email body (privacy: max 500 chars)
    
    Args:
        subject: Email subject line
        snippet: Email snippet (first 200 chars)
        body: Cleaned email body (first 500 chars, HTML removed)
        sender_domain: Sender domain
        sender_type: Sender type (COMPANY, ATS, HUMAN, NOISE)
        company_name: Known company name (if available)
        role: Known role/position (if available)
        thread_summary: Summary of thread history
        has_calendar: Whether calendar invite detected
        has_date: Whether date mentioned
        has_time: Whether time mentioned
    
    Returns:
        Formatted prompt string
    """
    prompt = f"""Classify this job application email into exactly ONE category.

CATEGORIES (STRICT ENUM - must be one of these):
- ACTIVE: Application confirmation, under review, general job-related communication
- REJECTED: Rejection, not selected, declined application
- INTERVIEW: Interview invitation, scheduling, interview-related communication
- OFFER: Job offer, compensation details, welcome message, onboarding
- GHOSTED: No response after extended period (only use if explicitly indicated)
- WITHDRAWN: Application withdrawn by candidate (explicit only)
- IGNORE: Non-job related, promotional, noise (should not reach LLM)

EMAIL DATA:
Subject: {subject}
Snippet: {snippet}
Body: {body[:500]}

CONTEXT:
Company: {company_name or "Unknown"}
Role: {role or "Unknown"}
Sender Domain: {sender_domain}
Sender Type: {sender_type}
{thread_summary}

STRUCTURAL SIGNALS:
Calendar Invite: {has_calendar}
Date Mentioned: {has_date}
Time Mentioned: {has_time}

OUTPUT FORMAT (STRICT JSON):
{{
  "status": "ACTIVE | INTERVIEW | REJECTED | OFFER | GHOSTED | WITHDRAWN",
  "confidence": 0.0-1.0,
  "reason": "Short human-readable explanation"
}}

WHY THESE CATEGORIES:
- ACTIVE: Default for job-related emails without clear decision
- REJECTED: Explicit rejection language ("unfortunately", "not moving forward")
- INTERVIEW: Scheduling, calendar invites, interview rounds
- OFFER: Compensation mentioned, offer letter, welcome message
- GHOSTED: Only if no response for 30+ days after ACTIVE/INTERVIEW
- WITHDRAWN: Only if candidate explicitly withdraws

Respond with ONLY valid JSON, no other text."""
    
    return prompt
