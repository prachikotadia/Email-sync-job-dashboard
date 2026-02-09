"""
Email Firewall - Pre-classification filter to block non-job emails
Runs BEFORE any ML models or classifiers to prevent pollution
"""
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Global firewall config (loaded once at startup)
_firewall_config = None

def load_firewall_config() -> Dict:
    """Load firewall configuration from YAML file"""
    global _firewall_config
    
    if _firewall_config is not None:
        return _firewall_config
    
    # Try multiple paths to find config file
    config_paths = [
        Path("config/email_firewall.yaml"),
        Path("../config/email_firewall.yaml"),
        Path("../../config/email_firewall.yaml"),
        Path("/app/config/email_firewall.yaml"),
        Path("/app/../config/email_firewall.yaml"),
    ]
    
    config_path = None
    for path in config_paths:
        if path.exists():
            config_path = path
            break
    
    if not config_path:
        logger.error("email_firewall.yaml not found in any expected location")
        # Return minimal default config
        _firewall_config = {
            "deny": {"domains_exact": [], "domains_substring": [], "keywords": []},
            "allow": {"ats_domains": [], "job_keywords": [], "sender_patterns": []},
            "strong_job_override": {"phrases": [], "require_job_term": True}
        }
        return _firewall_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            _firewall_config = config.get("firewall", {})
            logger.info(f"Loaded firewall config from {config_path}")
            return _firewall_config
    except Exception as e:
        logger.error(f"Failed to load firewall config: {e}")
        # Return minimal default config
        _firewall_config = {
            "deny": {"domains_exact": [], "domains_substring": [], "keywords": []},
            "allow": {"ats_domains": [], "job_keywords": [], "sender_patterns": []},
            "strong_job_override": {"phrases": [], "require_job_term": True}
        }
        return _firewall_config

def normalize_text(text: str) -> str:
    """Normalize text for matching (lowercase, strip, collapse whitespace)"""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)  # Collapse whitespace
    return text

def extract_domain(email: str) -> str:
    """Extract domain from email address"""
    if not email or '@' not in email:
        return ""
    return email.split('@')[1].lower().strip()

def extract_local_part(email: str) -> str:
    """Extract local part (before @) from email address"""
    if not email or '@' not in email:
        return ""
    return email.split('@')[0].lower().strip()

def matches_domain_exact(domain: str, deny_domains: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if domain exactly matches or is subdomain of any deny domain"""
    if not domain:
        return False, None
    
    domain_lower = domain.lower()
    
    for deny_domain in deny_domains:
        deny_domain_lower = deny_domain.lower()
        
        # Exact match
        if domain_lower == deny_domain_lower:
            return True, f"domain_exact:{deny_domain}"
        
        # Subdomain match (e.g., api.render.com matches render.com)
        if domain_lower.endswith('.' + deny_domain_lower):
            return True, f"domain_exact_subdomain:{deny_domain}"
    
    return False, None

def matches_domain_substring(domain: str, deny_substrings: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if domain contains any deny substring"""
    if not domain:
        return False, None
    
    domain_lower = domain.lower()
    
    for substring in deny_substrings:
        if substring.lower() in domain_lower:
            return True, f"domain_substring:{substring}"
    
    return False, None

def matches_keywords(text: str, keywords: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if text contains any deny keyword (case-insensitive)"""
    if not text:
        return False, None
    
    text_normalized = normalize_text(text)
    
    for keyword in keywords:
        keyword_normalized = normalize_text(keyword)
        if keyword_normalized in text_normalized:
            return True, f"keyword:{keyword}"
    
    return False, None

def matches_ats_domain(domain: str, ats_domains: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if domain matches any ATS domain (exact or subdomain)"""
    if not domain:
        return False, None
    
    domain_lower = domain.lower()
    
    for ats_domain in ats_domains:
        ats_domain_lower = ats_domain.lower()
        
        # Exact match
        if domain_lower == ats_domain_lower:
            return True, f"ats_domain:{ats_domain}"
        
        # Subdomain match
        if domain_lower.endswith('.' + ats_domain_lower):
            return True, f"ats_domain_subdomain:{ats_domain}"
    
    return False, None

def matches_job_keywords(text: str, job_keywords: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if text contains any strong job keyword"""
    if not text:
        return False, None
    
    text_normalized = normalize_text(text)
    
    for keyword in job_keywords:
        keyword_normalized = normalize_text(keyword)
        if keyword_normalized in text_normalized:
            return True, f"job_keyword:{keyword}"
    
    return False, None

def matches_sender_pattern(local_part: str, sender_patterns: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if local part matches any sender pattern"""
    if not local_part:
        return False, None
    
    local_part_lower = local_part.lower()
    
    for pattern in sender_patterns:
        pattern_lower = pattern.lower().rstrip('@')
        if local_part_lower.startswith(pattern_lower):
            return True, f"sender_pattern:{pattern}"
    
    return False, None

def matches_strong_job_override(text: str, override_phrases: List[str], require_job_term: bool, job_keywords: List[str]) -> Tuple[bool, Optional[str]]:
    """Check if text matches strong job override (unambiguous job decision phrases)"""
    if not text:
        return False, None
    
    text_normalized = normalize_text(text)
    matched_phrases = []
    
    for phrase in override_phrases:
        phrase_normalized = normalize_text(phrase)
        if phrase_normalized in text_normalized:
            matched_phrases.append(phrase)
    
    if not matched_phrases:
        return False, None
    
    # If require_job_term is True, also check for job keywords
    if require_job_term:
        has_job_term, _ = matches_job_keywords(text, job_keywords)
        if not has_job_term:
            return False, None
    
    return True, f"strong_job_override:{matched_phrases[0]}"

def firewall_decide(
    subject: str = "",
    snippet: str = "",
    from_email: str = "",
    from_domain: str = "",
    headers: Optional[Dict] = None
) -> Dict:
    """
    Firewall decision function - determines if email should enter job pipeline
    
    Args:
        subject: Email subject
        snippet: Email snippet/preview
        from_email: Full sender email address
        from_domain: Sender domain (extracted from from_email if not provided)
        headers: Optional email headers dict
    
    Returns:
        {
            "allow_job_pipeline": bool,
            "decision": "ALLOW" | "DENY",
            "category": "NON_JOB_AUTH" | "NON_JOB_PROMO" | "NON_JOB_SUPPORT" | "NON_JOB_BILLING" | "NON_JOB_DEPLOY" | "UNKNOWN" | "JOB",
            "matched_rules": [str],
            "reason": str
        }
    """
    config = load_firewall_config()
    
    # Normalize inputs
    subject = subject or ""
    snippet = snippet or ""
    from_email = from_email or ""
    
    # Extract domain if not provided
    if not from_domain and from_email:
        from_domain = extract_domain(from_email)
    
    # Extract local part
    local_part = extract_local_part(from_email)
    
    # Combine subject and snippet for text matching
    combined_text = f"{subject} {snippet}".strip()
    
    # Initialize result
    matched_rules = []
    deny_category = None
    
    # STEP 1: Check DENY rules (exact domains)
    deny_domains_exact = config.get("deny", {}).get("domains_exact", [])
    if from_domain:
        matched, rule = matches_domain_exact(from_domain, deny_domains_exact)
        if matched:
            matched_rules.append(rule)
            deny_category = "NON_JOB_DEPLOY" if any(d in from_domain for d in ["render", "netlify", "vercel", "railway", "heroku"]) else "UNKNOWN"
    
    # STEP 2: Check DENY rules (substring domains)
    if not matched_rules:  # Only check if no exact match yet
        deny_domains_substring = config.get("deny", {}).get("domains_substring", [])
        if from_domain:
            matched, rule = matches_domain_substring(from_domain, deny_domains_substring)
            if matched:
                matched_rules.append(rule)
                # Determine category based on substring
                if "auth" in from_domain or "login" in from_domain or "security" in from_domain:
                    deny_category = "NON_JOB_AUTH"
                elif "billing" in from_domain or "receipt" in from_domain or "invoice" in from_domain:
                    deny_category = "NON_JOB_BILLING"
                elif "newsletter" in from_domain or "promo" in from_domain or "marketing" in from_domain:
                    deny_category = "NON_JOB_PROMO"
                elif "support" in from_domain:
                    deny_category = "NON_JOB_SUPPORT"
                else:
                    deny_category = "UNKNOWN"
    
    # STEP 3: Check DENY rules (keywords)
    if not matched_rules:  # Only check if no domain match yet
        deny_keywords = config.get("deny", {}).get("keywords", [])
        matched, rule = matches_keywords(combined_text, deny_keywords)
        if matched:
            matched_rules.append(rule)
            # Determine category based on keyword
            text_lower = combined_text.lower()
            if any(kw in text_lower for kw in ["otp", "verification", "login", "password", "security", "2fa"]):
                deny_category = "NON_JOB_AUTH"
            elif any(kw in text_lower for kw in ["deploy", "build", "deployment"]):
                deny_category = "NON_JOB_DEPLOY"
            elif any(kw in text_lower for kw in ["invoice", "receipt", "payment", "billing", "charge"]):
                deny_category = "NON_JOB_BILLING"
            elif any(kw in text_lower for kw in ["newsletter", "unsubscribe", "promo", "sale", "discount"]):
                deny_category = "NON_JOB_PROMO"
            elif any(kw in text_lower for kw in ["ticket", "support", "case", "incident"]):
                deny_category = "NON_JOB_SUPPORT"
            else:
                deny_category = "UNKNOWN"
    
    # STEP 4: Check STRONG JOB OVERRIDE (if deny rule matched)
    if matched_rules:
        override_phrases = config.get("strong_job_override", {}).get("phrases", [])
        require_job_term = config.get("strong_job_override", {}).get("require_job_term", True)
        job_keywords = config.get("allow", {}).get("job_keywords", [])
        
        matched, rule = matches_strong_job_override(combined_text, override_phrases, require_job_term, job_keywords)
        if matched:
            # Override: This is definitely a job email despite deny rules
            matched_rules.append(rule)
            return {
                "allow_job_pipeline": True,
                "decision": "ALLOW",
                "category": "JOB",
                "matched_rules": matched_rules,
                "reason": f"Strong job override: {rule} (despite deny rules: {', '.join(matched_rules[:-1])})"
            }
    
    # STEP 5: If denied, return DENY immediately
    if matched_rules:
        return {
            "allow_job_pipeline": False,
            "decision": "DENY",
            "category": deny_category or "UNKNOWN",
            "matched_rules": matched_rules,
            "reason": f"Blocked by firewall: {', '.join(matched_rules)}"
        }
    
    # STEP 6: Check ALLOW rules (only if no deny rules matched)
    allow_rules = []
    
    # Check ATS domains
    ats_domains = config.get("allow", {}).get("ats_domains", [])
    if from_domain:
        matched, rule = matches_ats_domain(from_domain, ats_domains)
        if matched:
            allow_rules.append(rule)
    
    # Check job keywords
    job_keywords = config.get("allow", {}).get("job_keywords", [])
    matched, rule = matches_job_keywords(combined_text, job_keywords)
    if matched:
        allow_rules.append(rule)
    
    # Check sender patterns
    sender_patterns = config.get("allow", {}).get("sender_patterns", [])
    if local_part:
        matched, rule = matches_sender_pattern(local_part, sender_patterns)
        if matched:
            allow_rules.append(rule)
    
    # STEP 7: Decision logic
    if allow_rules:
        # At least one allow rule matched → ALLOW
        return {
            "allow_job_pipeline": True,
            "decision": "ALLOW",
            "category": "JOB",
            "matched_rules": allow_rules,
            "reason": f"Allowed by firewall: {', '.join(allow_rules)}"
        }
    else:
        # No allow rules matched → DENY (conservative default)
        return {
            "allow_job_pipeline": False,
            "decision": "DENY",
            "category": "UNKNOWN",
            "matched_rules": [],
            "reason": "No allow signals found - blocked by default (conservative)"
        }
