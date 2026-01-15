"""
Email body cleaner (RULE 3).

Removes signatures, disclaimers, and normalizes text.
"""
import re
import logging

logger = logging.getLogger(__name__)


def clean_email_body(body_text: str) -> str:
    """
    Clean email body (RULE 3).
    
    Removes:
    - Signatures
    - Disclaimers
    - Normalizes text
    
    Args:
        body_text: Raw email body text
        
    Returns:
        Cleaned body text
    """
    if not body_text:
        return ""
    
    # Remove common signature patterns
    signature_patterns = [
        r'--\s*$',  # "-- " at end of line
        r'Best regards.*$',
        r'Sincerely.*$',
        r'Regards.*$',
        r'Thanks.*$',
        r'Thank you.*$',
        r'This email.*confidential.*$',
        r'CONFIDENTIALITY.*$',
    ]
    
    lines = body_text.split('\n')
    cleaned_lines = []
    in_signature = False
    
    for line in lines:
        # Check if we've hit a signature marker
        if any(re.search(pattern, line, re.IGNORECASE | re.MULTILINE) for pattern in signature_patterns):
            in_signature = True
        
        # Skip signature lines
        if in_signature:
            continue
        
        # Remove excessive whitespace
        line = re.sub(r'\s+', ' ', line).strip()
        
        if line:
            cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Remove disclaimers (common legal text)
    disclaimer_patterns = [
        r'This message.*intended.*recipient.*',
        r'If you received.*error.*',
        r'Please do not.*reply.*',
        r'This is an automated.*',
    ]
    
    for pattern in disclaimer_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
    
    # Normalize whitespace
    cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)  # Multiple newlines -> double newline
    cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)  # Multiple spaces -> single space
    
    return cleaned_text.strip()
