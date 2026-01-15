"""
IMPROVED email classifier for job application emails.

This module implements balanced filtering with:
- Sender validation (ATS domains, company domains)
- Subject semantic checks (EXPANDED patterns)
- Body content analysis (first-person confirmation, EXPANDED patterns)
- Contextual keyword detection (fallback for edge cases)
- Scoring system (score >= 4 to accept - more lenient to capture all applications)
- Detailed logging

Key improvements:
- Lowered MIN_SCORE from 7 to 4 (more lenient)
- Added 50+ new positive patterns
- Added contextual keyword boost
- Enhanced sender validation
- Better ATS domain detection
"""
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)

# Known ATS domains (automatic +4 score)
ATS_DOMAINS = [
    'greenhouse.io',
    'lever.co',
    'workday.com',
    'myworkday.com',
    'smartrecruiters.com',
    'ashbyhq.com',
    'icims.com',
    'successfactors.com',
    'bamboohr.com',
    'jobvite.com',
    'talemetry.com',
    'jobs.lever.co',
    'jobs.greenhouse.io',
    'apply.workday.com',
    'recruiting.ultipro.com',
    'apply.icims.com',
    'app.jobvite.com',
    'ats.jobvite.com',
    'apply.jobvite.com',
    'jobs.smartrecruiters.com',
    'apply.smartrecruiters.com',
    'recruiting.paylocity.com',
    'recruiting.adp.com',
    'careers-page.com',
    'apply.careers-page.com',
    'recruiterbox.com',
    'apply.recruiterbox.com',
    'recruiterflow.com',
    'apply.recruiterflow.com',
]

# Newsletter/job alert domains (automatic rejection)
NEWSLETTER_DOMAINS = [
    'linkedin.com',
    'indeed.com',
    'glassdoor.com',
    'monster.com',
    'ziprecruiter.com',
    'dice.com',
    'simplyhired.com',
    'careerbuilder.com',
    'naukri.com',
]

# Positive subject patterns (application-specific) - EXPANDED
POSITIVE_SUBJECT_PATTERNS = [
    # Application confirmations
    (r'thank\s+you\s+for\s+applying', 4),
    (r'thanks\s+for\s+applying', 4),
    (r'application\s+received', 4),
    (r'application\s+submitted', 3),
    (r'your\s+application\s+for', 4),
    (r'application\s+for\s+', 3),
    (r'application\s+status', 3),
    (r'application\s+update', 3),
    (r'application\s+confirmation', 4),
    (r'application\s+acknowledgment', 3),
    (r'we\s+received\s+your\s+application', 4),
    (r'your\s+application\s+has\s+been\s+received', 4),
    # Interview invitations
    (r'interview\s+invitation', 6),
    (r'interview\s+invite', 6),
    (r'interview\s+scheduled', 6),
    (r'interview\s+request', 5),
    (r'schedule\s+an\s+interview', 5),
    (r'phone\s+screen', 5),
    (r'technical\s+interview', 5),
    (r'video\s+interview', 5),
    (r'virtual\s+interview', 5),
    (r'onsite\s+interview', 5),
    (r'on-site\s+interview', 5),
    # Rejections
    (r'we\s+regret\s+to\s+inform', 5),
    (r'regret\s+to\s+inform', 5),
    (r'not\s+selected', 4),
    (r'not\s+moving\s+forward', 4),
    (r'decided\s+not\s+to\s+move\s+forward', 4),
    (r'unfortunately', 3),
    (r'other\s+candidates', 3),
    # Next steps / Updates
    (r'next\s+steps', 4),
    (r'next\s+step', 4),
    (r'moving\s+forward', 4),
    (r'moving\s+to\s+next\s+stage', 4),
    # Assessments
    (r'assessment\s+invitation', 5),
    (r'assessment\s+request', 4),
    (r'test\s+invitation', 4),
    (r'coding\s+challenge', 4),
    (r'take-home\s+assignment', 4),
    (r'technical\s+assessment', 4),
    # Offers
    (r'offer\s+letter', 6),
    (r'job\s+offer', 6),
    (r'congratulations', 5),
    (r'we\s+would\s+like\s+to\s+offer', 6),
    (r'welcome\s+to\s+the\s+team', 5),
    # Status updates
    (r'application\s+under\s+review', 3),
    (r'under\s+review', 3),
    (r'still\s+being\s+considered', 3),
    (r'hiring\s+decision', 3),
    (r'background\s+check', 4),
    (r'reference\s+check', 3),
    # Generic but positive
    (r'regarding\s+your\s+application', 3),
    (r'about\s+your\s+application', 3),
    (r'your\s+candidacy', 3),
]

# Positive body patterns (first-person confirmation) - EXPANDED
POSITIVE_BODY_PATTERNS = [
    # Application confirmations
    (r'thank\s+you\s+for\s+applying\s+to', 5),
    (r'thanks\s+for\s+applying', 5),
    (r'we\s+have\s+received\s+your\s+application', 5),
    (r'we\s+received\s+your\s+application', 5),
    (r'your\s+application\s+has\s+been\s+received', 5),
    (r'application\s+submitted\s+successfully', 4),
    (r'your\s+application\s+for\s+.*\s+at\s+', 5),  # "your application for [ROLE] at [COMPANY]"
    (r'your\s+application\s+to\s+', 4),
    (r'application\s+for\s+the\s+position', 4),
    (r'application\s+for\s+the\s+role', 4),
    # Review/Status
    (r'we\s+reviewed\s+your\s+application', 4),
    (r'we\s+have\s+reviewed\s+your\s+application', 4),
    (r'after\s+reviewing\s+your\s+application', 4),
    (r'your\s+application\s+has\s+been\s+reviewed', 4),
    (r'application\s+under\s+review', 3),
    (r'under\s+review', 3),
    (r'still\s+being\s+considered', 3),
    (r'still\s+under\s+review', 3),
    (r'we\s+are\s+still\s+reviewing', 3),
    # Rejections
    (r'we\s+regret\s+to\s+inform\s+you', 5),
    (r'regret\s+to\s+inform', 5),
    (r'we\s+decided\s+not\s+to\s+move\s+forward', 4),
    (r'not\s+moving\s+forward', 4),
    (r'not\s+selected', 4),
    (r'other\s+candidates', 3),
    (r'unfortunately\s+we', 4),
    (r'after\s+careful\s+consideration', 4),
    # Interview invitations
    (r'we\s+would\s+like\s+to\s+invite\s+you', 6),
    (r'we\s+would\s+like\s+to\s+schedule', 5),
    (r'we\s+would\s+like\s+to\s+interview', 5),
    (r'invite\s+you\s+for\s+an\s+interview', 5),
    (r'schedule\s+an\s+interview', 5),
    (r'phone\s+screen', 4),
    (r'technical\s+interview', 5),
    (r'video\s+interview', 5),
    # Moving forward
    (r'we\s+decided\s+to\s+move\s+forward', 4),
    (r'moving\s+forward', 4),
    (r'moving\s+to\s+the\s+next\s+stage', 4),
    (r'next\s+steps', 4),
    (r'next\s+step', 4),
    # Offers
    (r'we\s+are\s+pleased\s+to\s+offer', 6),
    (r'we\s+would\s+like\s+to\s+offer', 6),
    (r'offer\s+letter', 5),
    (r'job\s+offer', 5),
    (r'congratulations', 5),
    (r'welcome\s+to\s+the\s+team', 5),
    # Generic positive
    (r'your\s+application\s+has\s+been', 3),
    (r'your\s+candidacy', 3),
    (r'we\s+appreciate\s+your\s+interest', 3),
    (r'regarding\s+your\s+application', 3),
    (r'about\s+your\s+application', 3),
    (r'we\'ll\s+get\s+back\s+to\s+you', 2),
    (r'we\s+will\s+get\s+back\s+to\s+you', 2),
    (r'we\s+will\s+contact\s+you', 2),
    (r'we\s+will\s+reach\s+out', 2),
    # Additional context
    (r'position\s+filled', 2),
    (r'compensation\s+discussion', 3),
    (r'background\s+check', 4),
    (r'reference\s+check', 3),
    (r'hiring\s+steps', 2),
    (r'onboarding', 3),
]

# Negative patterns (automatic rejection)
NEGATIVE_PATTERNS = [
    (r'jobs\s+you\s+may\s+like', -10),
    (r'job\s+alert', -10),
    (r'recommended\s+jobs', -10),
    (r'new\s+jobs\s+posted', -10),
    (r'career\s+opportunities', -8),
    (r'you\s+might\s+be\s+interested', -8),
    (r'we\s+found\s+jobs\s+matching', -8),
    (r'browse\s+opportunities', -8),
    (r'recommended\s+for\s+you', -8),
    (r'jobs\s+matching\s+your\s+profile', -8),
    (r'weekly\s+digest', -10),
    (r'daily\s+digest', -10),
    (r'monthly\s+digest', -10),
    (r'newsletter', -10),
    (r'unsubscribe', -5),
    (r'people\s+viewed\s+your\s+profile', -10),
    (r'viewed\s+your\s+profile', -10),
    (r'new\s+opportunities', -8),
    (r'explore\s+opportunities', -8),
    (r'join\s+our\s+talent\s+network', -8),
    (r'we\s+are\s+hiring', -8),  # Generic hiring ads without application context
    (r'cold\s+outreach', -8),
    (r'resume\s+services', -10),
    (r'career\s+tips', -8),
    (r'hr\s+branding', -8),
    (r'community\s+updates', -8),
]

class EmailCategory(str, Enum):
    """Email categories."""
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    ASSESSMENT = "ASSESSMENT"
    OFFER = "OFFER"
    OTHER_APPLICATION = "OTHER_APPLICATION"
    REJECTED_EMAIL = "REJECTED_EMAIL"  # For emails that don't pass filters


def extract_domain(email: str) -> str:
    """Extract domain from email address."""
    if '@' not in email:
        return email.lower()
    return email.split('@')[-1].lower().strip()


def extract_company_name(email_data: Dict[str, Any]) -> Tuple[str, float]:
    """
    RULE 6: Company name extraction with priority order.
    
    Priority order:
    1. Explicit company name in email body
    2. Email signature
    3. Sender display name
    4. Domain-based fallback
    
    Args:
        email_data: Dict with 'from', 'subject', 'body_text', 'to'
        
    Returns:
        (company_name, confidence) - never empty, confidence 0-1
    """
    from_email = (email_data.get('from') or '').strip()
    subject = (email_data.get('subject') or '').strip()
    body_text = (email_data.get('body_text') or '').strip()
    to_email = (email_data.get('to') or '').strip()
    
    import re
    
    # Personal email providers (exclude from company extraction)
    personal_domains = [
        'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 
        'icloud.com', 'aol.com', 'mail.com', 'protonmail.com',
        'yahoo.co.uk', 'outlook.co.uk', 'live.com', 'msn.com'
    ]
    
    # PRIORITY 1: Explicit company name in email body
    if body_text:
        # Look for explicit mentions: "at [Company]", "from [Company]", "[Company] team"
        explicit_patterns = [
            r'(?:at|from|with)\s+([A-Z][a-zA-Z0-9\s&\.]{2,40}(?:\s+(?:Inc|LLC|Corp|Ltd|Company))?)',
            r'([A-Z][a-zA-Z0-9\s&\.]{2,40})\s+team',
            r'([A-Z][a-zA-Z0-9\s&\.]{2,40})\s+recruiting',
            r'([A-Z][a-zA-Z0-9\s&\.]{2,40})\s+HR',
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, body_text[:1000], re.IGNORECASE)  # Check first 1000 chars
            if match:
                company = match.group(1).strip()
                # Clean up common suffixes
                company = re.sub(r'\s+(Inc|LLC|Corp|Ltd|Company)\.?$', '', company, flags=re.IGNORECASE)
                if company and len(company) > 1 and len(company) < 50:
                    # Exclude common words
                    if company.lower() not in ['team', 'hr', 'recruiting', 'talent', 'hiring', 'department']:
                        return (company.title(), 0.9)  # High confidence
    
    # PRIORITY 2: Email signature
    if body_text:
        # Look for signature patterns: "Best regards, [Name] | [Company]"
        signature_patterns = [
            r'\|.*?([A-Z][a-zA-Z0-9\s&\.]{2,40})',
            r'company[:\s]+([A-Z][a-zA-Z0-9\s&\.]{2,40})',
            r'from[:\s]+([A-Z][a-zA-Z0-9\s&\.]{2,40})',
            r'([A-Z][a-zA-Z0-9\s&\.]{2,40})\s*$',  # Last line of signature
        ]
        # Check last 500 chars (signature is usually at the end)
        signature_text = body_text[-500:] if len(body_text) > 500 else body_text
        for pattern in signature_patterns:
            match = re.search(pattern, signature_text, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                if company and len(company) > 1 and len(company) < 50:
                    if company.lower() not in ['team', 'hr', 'recruiting', 'talent', 'hiring']:
                        return (company.title(), 0.7)  # Medium confidence
    
    # PRIORITY 3: Sender display name
    if from_email:
        # Format: "Name <email@company.com>" or "Name (Company) <email>"
        # Try to extract from parentheses first
        paren_match = re.search(r'\(([^)]+)\)', from_email)
        if paren_match:
            company = paren_match.group(1).strip()
            if company and len(company) > 1 and len(company) < 50:
                return (company.title(), 0.6)
        
        # Try to extract from name part
        name_match = re.search(r'^(.+?)\s*[<\(]', from_email)
        if name_match:
            sender_name = name_match.group(1).strip()
            # If name contains company-like words, try to extract
            if any(word in sender_name.lower() for word in ['inc', 'llc', 'corp', 'ltd', 'company']):
                return (sender_name.title(), 0.5)
    
    # PRIORITY 4: Domain-based fallback
    if from_email and '@' in from_email:
        domain = extract_domain(from_email)
        if domain and domain not in personal_domains:
            # Remove common TLDs and extract company name
            parts = domain.split('.')
            if len(parts) >= 2:
                # Take the main domain part (e.g., "company" from "company.com")
                company_part = parts[-2] if parts[-1] in ['com', 'org', 'net', 'io', 'co', 'ai', 'tech', 'app'] else parts[0]
                # Remove common prefixes
                company_part = company_part.replace('careers', '').replace('jobs', '').replace('recruiting', '').replace('talent', '').replace('hr', '').replace('www', '')
                if company_part and len(company_part) > 1:
                    return (company_part.title(), 0.4)  # Lower confidence for domain-based
    
    # Default fallback (never empty)
    return ("Unknown Company", 0.0)


def validate_sender(sender: str) -> Tuple[int, str]:
    """
    Validate sender domain.
    Returns (score_adjustment, reason)
    """
    domain = extract_domain(sender)
    
    # Check ATS domains (higher score)
    for ats_domain in ATS_DOMAINS:
        if ats_domain in domain:
            return (4, f"ATS domain: {ats_domain}")
    
    # Check newsletter domains (automatic rejection signal)
    for newsletter_domain in NEWSLETTER_DOMAINS:
        if newsletter_domain in domain:
            return (-10, f"Newsletter domain: {newsletter_domain}")
    
    # Check for careers/jobs/talent/recruiting/hr in domain (higher score)
    if any(keyword in domain for keyword in ['careers', 'jobs', 'talent', 'recruit', 'recruiting', 'hr', 'hiring', 'people', 'human.resources']):
        return (2, f"Recruiting-related domain: {domain}")
    
    # Check for company domains (not personal email providers) - give small boost
    personal_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com', 'mail.com', 'protonmail.com']
    if domain not in personal_domains and '.' in domain:
        # Likely a company domain - give small boost if it's not a newsletter
        return (1, f"Company domain: {domain}")
    
    return (0, "")


def check_subject_semantic(subject: str) -> Tuple[int, List[str]]:
    """
    Check subject for semantic meaning.
    Returns (score, matched_patterns)
    """
    score = 0
    matched = []
    subject_lower = subject.lower()
    
    # Check positive patterns
    for pattern, points in POSITIVE_SUBJECT_PATTERNS:
        if re.search(pattern, subject_lower, re.IGNORECASE):
            score += points
            matched.append(f"+{points}: subject matches '{pattern}'")
    
    # Check negative patterns
    for pattern, penalty in NEGATIVE_PATTERNS:
        if re.search(pattern, subject_lower, re.IGNORECASE):
            score += penalty
            matched.append(f"{penalty}: subject matches negative '{pattern}'")
    
    return (score, matched)


def check_body_content(body_text: str) -> Tuple[int, List[str]]:
    """
    Check body for first-person confirmation.
    Returns (score, matched_patterns)
    """
    score = 0
    matched = []
    body_lower = body_text.lower()
    
    # Check positive patterns (first-person confirmation)
    for pattern, points in POSITIVE_BODY_PATTERNS:
        if re.search(pattern, body_lower, re.IGNORECASE):
            score += points
            matched.append(f"+{points}: body matches '{pattern}'")
    
    # Check negative patterns
    for pattern, penalty in NEGATIVE_PATTERNS:
        if re.search(pattern, body_lower, re.IGNORECASE):
            score += penalty
            matched.append(f"{penalty}: body matches negative '{pattern}'")
    
    return (score, matched)


def classify_status(subject: str, body: str, score: int) -> str:
    """
    Classify email status based on content.
    
    Returns one of: APPLIED, INTERVIEW, REJECTED, OFFER, GHOSTED, OTHER_APPLICATION
    """
    text = f"{subject} {body}".lower()
    
    # Interview (highest priority - check first)
    if any(pattern in text for pattern in ['interview', 'phone screen', 'technical interview', 'schedule a call', 'select a time', 'video call', 'zoom meeting']):
        return "INTERVIEW"
    
    # Assessment (part of interview process)
    if any(pattern in text for pattern in ['assessment', 'test invitation', 'coding challenge', 'take home', 'technical assessment']):
        return "ASSESSMENT"
    
    # Rejected (explicit rejection)
    if any(pattern in text for pattern in ['regret', 'not selected', 'decided not', 'not moving forward', 'other candidates', 'unfortunately', 'we will not be moving forward']):
        return "REJECTED"
    
    # Offer (explicit offer)
    if any(pattern in text for pattern in ['offer', 'congratulations', 'we would like to offer', 'welcome to the team', 'offer letter', 'compensation package']):
        return "OFFER"
    
    # Applied (explicit application confirmation)
    if any(pattern in text for pattern in ['application received', 'thank you for applying', 'application submitted', 'we have received your application']):
        return "APPLIED"
    
    # GHOSTED: No response after application (inferred from context)
    # This is typically detected by time-based analysis, but we can infer from certain patterns
    # For now, default to OTHER_APPLICATION - ghosted detection happens in application service
    
    # Other application-related (default for valid job emails that don't fit above)
    return "OTHER_APPLICATION"


def check_contextual_keywords(text: str) -> int:
    """
    Check for contextual job application keywords that might not match exact patterns.
    Returns additional score boost.
    """
    text_lower = text.lower()
    score = 0
    
    # High-value keywords (strong indicators)
    high_value = ['application', 'applied', 'candidate', 'position', 'role', 'job application']
    for keyword in high_value:
        if keyword in text_lower:
            score += 1
    
    # Medium-value keywords (moderate indicators)
    medium_value = ['resume', 'cv', 'interview', 'hiring', 'recruiter', 'recruitment']
    for keyword in medium_value:
        if keyword in text_lower:
            score += 0.5
    
    return int(score)


def classify_email_strict(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    IMPROVED email classification with more lenient scoring to capture ALL job application emails.
    
    Returns:
        {
            'label': EmailCategory,
            'confidence': float (0.0-1.0),
            'score': int,
            'stored': bool,
            'reasons': List[str],
            'rejection_reason': Optional[str],
            'status': str
        }
    """
    subject = (email_data.get("subject") or "").strip()
    from_email = (email_data.get("from") or "").strip()
    snippet = (email_data.get("snippet") or "").strip()
    body_text = (email_data.get("body_text") or snippet).strip()
    
    # Combine all text for contextual analysis
    combined_text = f"{subject} {body_text}".lower()
    
    # Initialize score
    total_score = 0
    reasons = []
    
    # 1. Sender validation
    sender_score, sender_reason = validate_sender(from_email)
    total_score += sender_score
    if sender_reason:
        reasons.append(f"{sender_score:+d}: {sender_reason}")
    
    # Early rejection if sender is clearly a newsletter
    if sender_score <= -10:
        return {
            'label': EmailCategory.REJECTED_EMAIL.value,
            'confidence': 0.0,
            'score': total_score,
            'stored': False,
            'reasons': reasons,
            'rejection_reason': f"Sender validation failed: {sender_reason}",
            'status': 'REJECTED_EMAIL'
        }
    
    # 2. Subject semantic check
    subject_score, subject_matches = check_subject_semantic(subject)
    total_score += subject_score
    reasons.extend(subject_matches)
    
    # 3. Body content analysis
    body_score, body_matches = check_body_content(body_text)
    total_score += body_score
    reasons.extend(body_matches)
    
    # 4. Contextual keyword boost (for emails that mention job-related terms)
    contextual_score = check_contextual_keywords(combined_text)
    total_score += contextual_score
    if contextual_score > 0:
        reasons.append(f"+{contextual_score}: contextual job-related keywords")
    
    # 5. Score evaluation (LOWERED THRESHOLD: score >= 4 to accept - more lenient)
    MIN_SCORE = 4
    if total_score < MIN_SCORE:
        return {
            'label': EmailCategory.REJECTED_EMAIL.value,
            'confidence': 0.0,
            'score': total_score,
            'stored': False,
            'reasons': reasons,
            'rejection_reason': f"Score {total_score} < {MIN_SCORE} (minimum required)",
            'status': 'REJECTED_EMAIL'
        }
    
    # 6. Status classification
    status = classify_status(subject, body_text, total_score)
    
    # Map status to category
    status_map = {
        'APPLIED': EmailCategory.APPLIED,
        'INTERVIEW': EmailCategory.INTERVIEW,
        'REJECTED': EmailCategory.REJECTED,
        'ASSESSMENT': EmailCategory.ASSESSMENT,
        'OFFER': EmailCategory.OFFER,
        'OTHER_APPLICATION': EmailCategory.OTHER_APPLICATION,
    }
    
    category = status_map.get(status, EmailCategory.OTHER_APPLICATION)
    
    # Confidence is score normalized to 0-1 (score 4-15 range maps to 0.6-1.0)
    confidence = min(1.0, 0.6 + (total_score - MIN_SCORE) * 0.04)
    
    return {
        'label': category.value,
        'confidence': confidence,
        'score': total_score,
        'stored': True,
        'reasons': reasons,
        'rejection_reason': None,
        'status': status
    }
