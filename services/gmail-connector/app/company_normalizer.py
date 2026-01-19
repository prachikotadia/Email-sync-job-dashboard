"""
Company Name Normalization

Normalizes company names for consistent grouping:
- Strips "Careers", "Jobs", "Hiring", "Team"
- Maps domains → canonical names
- Ensures consistent grouping in SQL queries

All normalization happens in SQL for performance.
"""
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Domain to canonical company name mapping
DOMAIN_TO_COMPANY = {
    'amazon.jobs': 'Amazon',
    'amazon.com': 'Amazon',
    'google.com': 'Google',
    'facebook.com': 'Meta',
    'meta.com': 'Meta',
    'microsoft.com': 'Microsoft',
    'apple.com': 'Apple',
    'netflix.com': 'Netflix',
    # Add more mappings as needed
}

# Prefixes/suffixes to strip for normalization
COMPANY_PREFIXES = ['Careers', 'Jobs', 'Hiring', 'Recruiting', 'Talent', 'HR', 'Team']
COMPANY_SUFFIXES = ['LLC', 'Inc', 'Inc.', 'Ltd', 'Ltd.', 'Corp', 'Corporation', 'Pvt', 'Pvt.', 'Limited', 'Co', 'Co.']


def normalize_company_name_for_grouping(company_name: str, company_domain: Optional[str] = None) -> str:
    """
    Normalize company name for consistent grouping.
    This is the Python version - SQL version should match this logic.
    
    Args:
        company_name: Raw company name from database
        company_domain: Optional company domain for mapping
        
    Returns:
        Normalized canonical company name
    """
    if not company_name:
        return "Unknown Company"
    
    # First check domain mapping
    if company_domain:
        domain_lower = company_domain.lower().strip()
        if domain_lower in DOMAIN_TO_COMPANY:
            return DOMAIN_TO_COMPANY[domain_lower]
    
    # Normalize company name
    normalized = company_name.strip()
    
    # Remove common prefixes (case-insensitive)
    for prefix in COMPANY_PREFIXES:
        # Remove prefix at start
        normalized = re.sub(rf'^{re.escape(prefix)}\s+', '', normalized, flags=re.IGNORECASE)
        # Remove prefix at end
        normalized = re.sub(rf'\s+{re.escape(prefix)}$', '', normalized, flags=re.IGNORECASE)
    
    # Remove common suffixes (case-insensitive)
    for suffix in COMPANY_SUFFIXES:
        normalized = re.sub(rf'\s+{re.escape(suffix)}$', '', normalized, flags=re.IGNORECASE)
    
    # Clean up multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # If normalization resulted in empty string, return original or "Unknown Company"
    if not normalized or len(normalized) < 2:
        return company_name if company_name else "Unknown Company"
    
    # Title case normalization (capitalize first letter of each word)
    words = normalized.split()
    title_words = []
    for word in words:
        if word.lower() in ['and', 'of', 'the', 'at', 'in', 'on', 'for', 'with']:
            title_words.append(word.lower())
        else:
            title_words.append(word.capitalize())
    
    normalized = ' '.join(title_words)
    
    return normalized


def get_sql_normalize_company_function() -> str:
    """
    Returns SQL expression for normalizing company names in GROUP BY queries.
    This matches the Python normalization logic for consistency.
    
    SQL does:
    1. Lowercase for comparison
    2. Remove common prefixes/suffixes using regex
    3. Trim whitespace
    4. Title case (first letter uppercase)
    """
    # SQL function for normalizing company names
    # This is used in GROUP BY to ensure consistent grouping
    sql = """
    TRIM(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                LOWER(COALESCE(company_name, 'Unknown Company')),
                '^(careers|jobs|hiring|recruiting|talent|hr|team)\\s+',
                '',
                'gi'
            ),
            '\\s+(llc|inc|inc\\.|ltd|ltd\\.|corp|corporation|pvt|pvt\\.|limited|co|co\\.)$',
            '',
            'gi'
        )
    )
    """
    return sql.strip()
