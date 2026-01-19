"""
URL Validation and Normalization for Profile Links
Strict validation rules to prevent broken links in database.
"""
import re
from typing import Tuple, Optional
from urllib.parse import urlparse, urlunparse
import logging

logger = logging.getLogger(__name__)

# Allowed URL schemes
ALLOWED_SCHEMES = {'http', 'https'}

# Blocked patterns (security)
BLOCKED_PATTERNS = [
    r'javascript:',
    r'data:',
    r'vbscript:',
    r'file:',
    r'about:',
]

def normalize_url(url: str) -> Optional[str]:
    """
    Normalize URL by adding https:// if missing scheme.
    
    Rules:
    - If starts with http:// or https:// → keep as-is
    - If starts with // → add https:
    - If starts with domain → add https://
    - Returns None if invalid
    """
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    if not url:
        return None
    
    # Check for blocked patterns
    url_lower = url.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, url_lower):
            logger.warning(f"Blocked URL pattern detected: {url}")
            return None
    
    # Already has scheme
    if url.startswith(('http://', 'https://')):
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return None
        # Normalize to https for security
        if parsed.scheme == 'http':
            parsed = parsed._replace(scheme='https')
        return urlunparse(parsed)
    
    # Protocol-relative URL (//example.com)
    if url.startswith('//'):
        parsed = urlparse(f'https:{url}')
        return urlunparse(parsed._replace(scheme='https'))
    
    # No scheme - add https://
    parsed = urlparse(f'https://{url}')
    if not parsed.netloc:
        # Invalid domain
        return None
    
    return urlunparse(parsed._replace(scheme='https'))

def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate URL and return (is_valid, normalized_url_or_error_message).
    
    Validation rules:
    - Must be a valid URL format
    - Must have valid domain (netloc)
    - Must use http:// or https:// (auto-normalized)
    - Must not contain blocked patterns
    - Returns (True, normalized_url) if valid
    - Returns (False, error_message) if invalid
    """
    if not url or not isinstance(url, str):
        return False, "URL is required"
    
    url = url.strip()
    if not url:
        return False, "URL cannot be empty"
    
    # Normalize URL
    normalized = normalize_url(url)
    if not normalized:
        return False, "Invalid URL format. Please enter a valid URL (e.g., linkedin.com/in/yourprofile)"
    
    # Parse normalized URL to validate
    try:
        parsed = urlparse(normalized)
        
        # Must have netloc (domain)
        if not parsed.netloc:
            return False, "Invalid URL: missing domain"
        
        # Must use allowed scheme
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False, f"Invalid URL scheme. Only http:// and https:// are allowed"
        
        # Domain must not be empty after parsing
        domain_parts = parsed.netloc.split('.')
        if len(domain_parts) < 2 or any(not part for part in domain_parts):
            return False, "Invalid URL: invalid domain name"
        
        # Success
        return True, normalized
        
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False, "Invalid URL format. Please check your URL and try again."

def detect_platform_from_url(url: str) -> Optional[str]:
    """
    Auto-detect platform type from URL.
    Returns 'linkedin', 'github', 'portfolio', or None.
    """
    if not url:
        return None
    
    url_lower = url.lower()
    
    if 'linkedin.com' in url_lower:
        return 'linkedin'
    elif 'github.com' in url_lower:
        return 'github'
    elif any(domain in url_lower for domain in ['portfolio', 'personal', 'website', 'site']):
        # Heuristic: if URL contains portfolio/personal keywords, assume portfolio
        # This is best-effort, user can override
        return 'portfolio'
    
    return None
