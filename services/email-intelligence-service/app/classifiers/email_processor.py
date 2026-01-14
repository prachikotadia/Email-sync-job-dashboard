"""
Email text extraction and normalization utilities.
"""
import re
import html
from typing import Dict, Any
from email.utils import parsedate_to_datetime
from datetime import datetime


def extract_email_text(email_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract and normalize text from email data.
    
    Args:
        email_data: Email data from Gmail API (format='full')
        
    Returns:
        Dict with:
        - subject: Normalized subject
        - body_text: Normalized body text (plain text)
        - combined_text: Subject + body (for searching)
        - sender_email: Sender email address
        - sender_domain: Sender domain
    """
    # Extract subject
    headers = email_data.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
    
    # Extract sender
    sender_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
    sender_domain = ''
    if '@' in sender_email:
        # Extract email from "Name <email@domain.com>" format
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', sender_email)
        if email_match:
            sender_email = email_match.group(0)
            sender_domain = sender_email.split('@')[1]
    
    # Extract body
    body_text = ''
    payload = email_data.get('payload', {})
    
    # Try to get plain text body
    parts = payload.get('parts', [])
    if parts:
        for part in parts:
            mime_type = part.get('mimeType', '')
            body_data = part.get('body', {}).get('data', '')
            
            if mime_type == 'text/plain' and body_data:
                import base64
                try:
                    body_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                    break
                except:
                    pass
    else:
        # Single part message
        mime_type = payload.get('mimeType', '')
        body_data = payload.get('body', {}).get('data', '')
        if mime_type == 'text/plain' and body_data:
            import base64
            try:
                body_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
            except:
                pass
    
    # Normalize text
    subject_normalized = normalize_text(subject)
    body_normalized = normalize_text(body_text)
    combined_text = f"{subject_normalized} {body_normalized}".strip()
    
    return {
        "subject": subject_normalized,
        "body_text": body_normalized,
        "combined_text": combined_text,
        "sender_email": sender_email,
        "sender_domain": sender_domain,
    }


def normalize_text(text: str) -> str:
    """
    Normalize email text for classification.
    
    Steps:
    1. Convert to lowercase
    2. Decode HTML entities
    3. Remove HTML tags
    4. Remove email signatures
    5. Remove quoted replies
    6. Remove extra whitespace
    7. Deduplicate repeated lines
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', ' ', text)
    
    # Remove email addresses (but keep domain info)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', ' ', text)
    
    # Remove signatures (common patterns)
    signature_patterns = [
        r'sent from my .+',
        r'best regards.*',
        r'regards,.*',
        r'thank you,.*',
        r'--.*',  # Email signature separator
    ]
    for pattern in signature_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove quoted replies (lines starting with >)
    lines = text.split('\n')
    lines = [line for line in lines if not line.strip().startswith('>')]
    text = '\n'.join(lines)
    
    # Remove "On ... wrote:" pattern (common in email replies)
    text = re.sub(r'on .+ wrote:.*', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Deduplicate repeated lines (simple approach)
    lines = text.split('\n')
    seen = set()
    unique_lines = []
    for line in lines:
        line_stripped = line.strip()
        if line_stripped and line_stripped not in seen:
            seen.add(line_stripped)
            unique_lines.append(line)
    text = '\n'.join(unique_lines)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


def extract_email_metadata(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metadata from email (dates, thread info, etc.)
    """
    headers = email_data.get('payload', {}).get('headers', [])
    
    # Extract date
    date_str = next((h['value'] for h in headers if h['name'] == 'Date'), None)
    received_at = None
    if date_str:
        try:
            received_at = parsedate_to_datetime(date_str)
        except:
            received_at = datetime.utcnow()
    else:
        received_at = datetime.utcnow()
    
    # Extract thread ID
    thread_id = email_data.get('threadId', '')
    
    # Extract email ID
    email_id = email_data.get('id', '')
    
    return {
        "received_at": received_at,
        "thread_id": thread_id,
        "email_id": email_id,
    }
