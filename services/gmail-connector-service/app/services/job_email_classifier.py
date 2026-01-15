"""
PRODUCTION-GRADE Job Email Classifier - ZERO FALSE NEGATIVES POLICY

CORE PRINCIPLE: When in doubt, INCLUDE - not exclude.

This classifier implements:
1. Very permissive job detection (ANY hint = job-related)
2. Stores ALL job-related emails (never skips)
3. OTHER_JOB_RELATED as default for uncertain emails
4. Only marks as NON_JOB if 100% certain it's not job-related
"""
import re
import logging
from typing import Dict, Any, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job application email statuses - OTHER_JOB_RELATED is default for uncertain."""
    APPLIED = "APPLIED"
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    REJECTED = "REJECTED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    ACCEPTED = "ACCEPTED"
    WITHDRAWN = "WITHDRAWN"
    ASSESSMENT = "ASSESSMENT"
    SCREENING = "SCREENING"
    FOLLOW_UP = "FOLLOW_UP"
    OTHER_JOB_RELATED = "OTHER_JOB_RELATED"  # DEFAULT for uncertain job emails
    NON_JOB = "NON_JOB"  # Only if 100% certain


# ATS domains (automatic job email indicator)
ATS_DOMAINS = [
    'greenhouse.io', 'lever.co', 'ashbyhq.com', 'workable.com', 'icims.com',
    'smartrecruiters.com', 'workday.com', 'myworkday.com', 'successfactors.com',
    'bamboohr.com', 'jobvite.com', 'talemetry.com', 'jobs.lever.co',
    'jobs.greenhouse.io', 'apply.workday.com', 'recruiting.ultipro.com',
    'apply.icims.com', 'app.jobvite.com', 'ats.jobvite.com',
    'apply.jobvite.com', 'jobs.smartrecruiters.com', 'apply.smartrecruiters.com',
    'recruiting.paylocity.com', 'recruiting.adp.com', 'careers-page.com',
    'apply.careers-page.com', 'recruiterbox.com', 'apply.recruiterbox.com',
    'recruiterflow.com', 'apply.recruiterflow.com',
]

# Job-related keywords (VERY BROAD - any mention = job-related)
# ONE MATCH IS ENOUGH to classify as job-related
JOB_KEYWORDS = [
    # Application keywords
    'apply', 'applied', 'application', 'applicant', 'applications',
    'candidate', 'candidates', 'candidacy',
    # Role/Position keywords
    'role', 'roles', 'position', 'positions', 'job', 'jobs',
    # Interview keywords
    'interview', 'interviews', 'interviewing', 'interviewed',
    # Recruiter keywords
    'recruiter', 'recruiters', 'recruiting', 'recruitment',
    'hiring', 'hiring team', 'talent acquisition', 'talent',
    # Career keywords
    'career', 'careers',
    # Assessment keywords
    'assessment', 'assessments', 'technical round', 'coding test', 
    'challenge', 'challenges', 'assignment', 'assignments',
    # Offer keywords
    'offer', 'offers', 'offered',
    # Rejection keywords
    'rejection', 'rejected', 'regret', 'unfortunately',
    # Status keywords
    'thank you for your interest', 'we reviewed your application',
    'next steps', 'screening', 'screenings',
    'hr', 'human resources', 'people team',
    'thank you for applying', 'your application',
    'we received your application', 'application status',
    'position you applied', 'job application',
    # ATS keywords
    'ats', 'greenhouse', 'lever', 'workday', 'ashby',
    'smartrecruiters', 'icims', 'bamboohr',
]

# Sender indicators (careers, talent, recruiting, etc.)
SENDER_INDICATORS = [
    'careers', 'talent', 'recruiting', 'hiring', 'hr', 'people',
    'recruiter', 'recruiters', 'talent.acquisition',
]

# Hard rejection patterns (ONLY if 100% certain it's not job-related)
HARD_REJECT_PATTERNS = [
    (r'verification\s+code', True),
    (r'otp\s+code', True),
    (r'password\s+reset', True),
    (r'security\s+code', True),
    (r'two-factor', True),
    (r'receipt\s+for', True),
    (r'invoice\s+#', True),
    (r'order\s+confirmation', True),
    (r'payment\s+received', True),
    (r'\[github\]', True),  # GitHub notifications
    (r'\[jira\]', True),  # Jira notifications
    (r'\[slack\]', True),  # Slack notifications
]


def is_job_related(email_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    STEP 1: AUTO-JOB DETECTION (VERY PERMISSIVE)
    
    Mark email as JOB_RELATED if ANY of the following are true:
    - Mentions job keywords
    - Sender domain is ATS
    - Sender contains careers/talent/recruiting/hiring/hr
    - "Thank you for your interest"
    - "We reviewed your application"
    
    Returns:
        (is_job_related, reason)
    """
    from_email = (email_data.get('from') or '').lower()
    subject = (email_data.get('subject') or '').lower()
    body_text = (email_data.get('body_text') or '').lower()
    snippet = (email_data.get('snippet') or '').lower()
    
    combined_text = f"{subject} {body_text} {snippet}".lower()
    
    # Check ATS domain (automatic job email)
    if '@' in from_email:
        domain = from_email.split('@')[-1].lower()
        for ats_domain in ATS_DOMAINS:
            if ats_domain in domain or ats_domain in from_email:
                return (True, f"ATS domain: {ats_domain}")
    
    # Check sender indicators
    for indicator in SENDER_INDICATORS:
        if indicator in from_email:
            return (True, f"Sender contains: {indicator}")
    
    # Check for job keywords (ANY mention = job-related)
    for keyword in JOB_KEYWORDS:
        if keyword in combined_text:
            return (True, f"Contains keyword: {keyword}")
    
    # Check for common phrases
    phrases = [
        'thank you for your interest',
        'we reviewed your application',
        'we received your application',
        'your application',
        'next steps',
    ]
    for phrase in phrases:
        if phrase in combined_text:
            return (True, f"Contains phrase: {phrase}")
    
    # Default: NOT job-related (only if no indicators found)
    return (False, "No job-related indicators found")


def classify_status(email_data: Dict[str, Any]) -> Tuple[JobStatus, str]:
    """
    STEP 2: STATUS CLASSIFICATION
    
    Classify into ONE status based on content.
    If uncertain → OTHER_JOB_RELATED (default)
    """
    subject = (email_data.get('subject') or '').lower()
    body_text = (email_data.get('body_text') or '').lower()
    snippet = (email_data.get('snippet') or '').lower()
    combined_text = f"{subject} {body_text} {snippet}".lower()
    
    # REJECTED (highest priority)
    if any(p in combined_text for p in [
        'we will not be moving forward',
        'unfortunately',
        'decided to pursue other candidates',
        'not selected',
        'not moving forward',
        'regret to inform',
    ]):
        return (JobStatus.REJECTED, "Rejection detected")
    
    # OFFER
    if any(p in combined_text for p in [
        'offer', 'compensation', 'salary', 'joining', 'congratulations',
        'welcome to the team', 'we are pleased to offer',
    ]):
        return (JobStatus.OFFER, "Offer detected")
    
    # ACCEPTED
    if any(p in combined_text for p in [
        'accepted the offer', 'accepting the position',
        'excited to join', 'looking forward to starting',
    ]):
        return (JobStatus.ACCEPTED, "Offer acceptance detected")
    
    # INTERVIEW
    if any(p in combined_text for p in [
        'interview', 'schedule', 'calendly', 'availability',
        'meet', 'round', 'phone screen', 'video interview',
        'onsite interview', 'technical interview',
    ]):
        return (JobStatus.INTERVIEW, "Interview invitation detected")
    
    # ASSESSMENT
    if any(p in combined_text for p in [
        'test', 'assignment', 'challenge', 'hackerrank',
        'codility', 'leetcode', 'technical assessment',
        'coding challenge', 'take-home',
    ]):
        return (JobStatus.ASSESSMENT, "Assessment detected")
    
    # SCREENING
    if any(p in combined_text for p in [
        'screening', 'initial screening', 'phone screen',
    ]):
        return (JobStatus.SCREENING, "Screening detected")
    
    # APPLICATION_RECEIVED / APPLIED
    if any(p in combined_text for p in [
        'thank you for applying', 'application received',
        'application submitted', 'submission confirmed',
        'we received your application', 'your application has been received',
    ]):
        return (JobStatus.APPLICATION_RECEIVED, "Application confirmation detected")
    
    # FOLLOW_UP
    if any(p in combined_text for p in [
        'checking in', 'following up', 'update on your application',
        'status update', 'application update',
    ]):
        return (JobStatus.FOLLOW_UP, "Follow-up detected")
    
    # Default: OTHER_JOB_RELATED (for any job-related email that doesn't match above)
    return (JobStatus.OTHER_JOB_RELATED, "Job-related but unclear status")


def extract_company_name(email_data: Dict[str, Any]) -> str:
    """
    STEP 3: COMPANY EXTRACTION
    
    Extract company name using:
    1. Explicit mention in body
    2. Email signature
    3. Sender domain (remove no-reply, mail, jobs, careers)
    
    If not found → "UNKNOWN" (DO NOT fail)
    """
    from_email = (email_data.get('from') or '').lower()
    body_text = (email_data.get('body_text') or '').lower()
    subject = (email_data.get('subject') or '').lower()
    
    # Try to extract from sender domain
    if '@' in from_email:
        domain = from_email.split('@')[-1].lower()
        # Remove common prefixes
        domain = domain.replace('no-reply@', '').replace('noreply@', '')
        domain = domain.replace('mail.', '').replace('jobs.', '').replace('careers.', '')
        domain = domain.replace('apply.', '').replace('recruiting.', '')
        
        # If domain looks like a company domain (not gmail/yahoo/etc)
        if domain and domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']:
            # Extract company name from domain (e.g., "google.com" -> "Google")
            company = domain.split('.')[0]
            if company and len(company) > 2:
                return company.title()
    
    # Try to extract from subject (e.g., "Application at Google")
    if 'at ' in subject or 'at ' in body_text:
        match = re.search(r'at\s+([A-Z][a-zA-Z\s]+)', subject + ' ' + body_text, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
    
    # Default: UNKNOWN (DO NOT fail)
    return "UNKNOWN"


def is_hard_rejected(email_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Hard rejection check (ONLY if 100% certain it's not job-related).
    
    Returns:
        (should_reject, reason)
    """
    subject = (email_data.get('subject') or '').lower()
    body_text = (email_data.get('body_text') or '').lower()
    snippet = (email_data.get('snippet') or '').lower()
    combined_text = f"{subject} {body_text} {snippet}".lower()
    
    # Check hard rejection patterns
    for pattern, _ in HARD_REJECT_PATTERNS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return (True, f"Hard reject: {pattern}")
    
    return (False, None)


def classify_job_email(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    MAIN CLASSIFICATION FUNCTION - ZERO FALSE NEGATIVES POLICY.
    
    CORE RULE: If ANY hint of job-related → classify as job-related.
    
    Pipeline:
    1. Hard rejection check (ONLY if 100% certain)
    2. Job detection (VERY permissive)
    3. Status classification
    4. Company extraction (UNKNOWN if not found)
    
    Returns:
        {
            'status': JobStatus,
            'confidence': 'high' | 'medium' | 'low',
            'reason': str,
            'is_job_email': bool,
            'should_store': bool,  # ALWAYS True for job-related
            'company': str,
        }
    """
    # STEP 1: Hard rejection (ONLY if 100% certain)
    is_rejected, reject_reason = is_hard_rejected(email_data)
    if is_rejected:
        logger.info(f"Email {email_data.get('id', 'unknown')[:10]}... → STORED → NON_JOB | Reason: {reject_reason}")
        return {
            'status': JobStatus.NON_JOB,
            'confidence': 'high',
            'reason': reject_reason,
            'is_job_email': False,
            'should_store': True,  # Store even non-job for completeness
            'company': 'UNKNOWN',
        }
    
    # STEP 2: Job detection (VERY PERMISSIVE)
    is_job, job_reason = is_job_related(email_data)
    
    if not is_job:
        # Only mark as NON_JOB if we're 100% certain
        logger.info(f"Email {email_data.get('id', 'unknown')[:10]}... → STORED → NON_JOB | Reason: {job_reason}")
        return {
            'status': JobStatus.NON_JOB,
            'confidence': 'medium',
            'reason': job_reason,
            'is_job_email': False,
            'should_store': True,  # Store for completeness
            'company': 'UNKNOWN',
        }
    
    # STEP 3: Status classification
    status, status_reason = classify_status(email_data)
    
    # STEP 4: Company extraction
    company = extract_company_name(email_data)
    
    # Determine confidence
    from_email = (email_data.get('from') or '').lower()
    if any(ats in from_email for ats in ATS_DOMAINS):
        confidence = 'high'
    elif status != JobStatus.OTHER_JOB_RELATED:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    reason = f"{status_reason} | {job_reason}"
    
    # LOG EVERY DECISION
    logger.info(f"Email {email_data.get('id', 'unknown')[:10]}... → STORED → {status.value} | "
                f"Company: {company} | Confidence: {confidence} | Reason: {reason}")
    
    return {
        'status': status,
        'confidence': confidence,
        'reason': reason,
        'is_job_email': True,
        'should_store': True,  # ALWAYS STORE job-related emails
        'company': company,
    }
