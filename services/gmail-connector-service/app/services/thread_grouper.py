"""
RULE 7: Thread & Timeline Grouping.

Groups emails by:
- user_id
- company_id
- job_title (if available)

Sorts timeline:
Applied → Interview → Offer / Rejection
"""
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Status priority for timeline sorting (lower = earlier in process)
STATUS_PRIORITY = {
    'Applied': 1,
    'Other_Job_Update': 2,
    'Interview': 3,
    'Rejected': 4,
    'Accepted/Offer': 5,
    'Ghosted': 6,
}


def group_emails_by_company_and_role(emails: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    RULE 7: Group emails by company and role.
    
    Groups emails by:
    - company_name (normalized)
    - role_title (if available)
    
    Returns:
        Dict with key: "{company_name}||{role_title}" and value: list of emails
    """
    groups = {}
    
    for email in emails:
        company_name = email.get('company_name', 'Unknown Company')
        role_title = email.get('role', '') or ''
        
        # Normalize company name (remove common suffixes)
        company_name = normalize_company_name(company_name)
        
        # Create group key
        group_key = f"{company_name}||{role_title}" if role_title else f"{company_name}||"
        
        if group_key not in groups:
            groups[group_key] = []
        
        groups[group_key].append(email)
    
    logger.info(f"[THREAD GROUPING] Grouped {len(emails)} emails into {len(groups)} company/role groups")
    
    return groups


def normalize_company_name(company_name: str) -> str:
    """Normalize company name (RULE 6)."""
    if not company_name:
        return "Unknown Company"
    
    # Remove common suffixes
    import re
    company_name = re.sub(r'\s+(Inc|LLC|Corp|Ltd|Company|Co)\.?$', '', company_name, flags=re.IGNORECASE)
    
    # Normalize variations
    company_name = company_name.strip()
    
    return company_name


def sort_timeline_by_status(emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    RULE 7: Sort timeline by status priority and date.
    
    Timeline order:
    Applied → Interview → Offer / Rejection
    
    Returns:
        Sorted list of emails
    """
    def sort_key(email: Dict[str, Any]) -> Tuple[int, datetime]:
        status = email.get('application_status', 'Applied')
        priority = STATUS_PRIORITY.get(status, 99)
        
        # Parse received_at
        received_at_str = email.get('received_at', '')
        try:
            if isinstance(received_at_str, str):
                received_at = datetime.fromisoformat(received_at_str.replace('Z', '+00:00'))
            else:
                received_at = received_at_str
        except:
            received_at = datetime.min
        
        return (priority, received_at)
    
    sorted_emails = sorted(emails, key=sort_key)
    
    logger.info(f"[THREAD GROUPING] Sorted {len(sorted_emails)} emails by status and date")
    
    return sorted_emails


def group_emails_by_thread(emails: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    RULE 7: Group emails by thread_id.
    
    Returns:
        Dict with key: thread_id and value: list of emails in that thread
    """
    threads = {}
    
    for email in emails:
        thread_id = email.get('thread_id', '')
        if not thread_id:
            # If no thread_id, create a unique one based on company + role
            company_name = email.get('company_name', 'Unknown')
            role = email.get('role', '')
            thread_id = f"single_{company_name}_{role}_{email.get('email_id', '')}"
        
        if thread_id not in threads:
            threads[thread_id] = []
        
        threads[thread_id].append(email)
    
    logger.info(f"[THREAD GROUPING] Grouped {len(emails)} emails into {len(threads)} threads")
    
    return threads


def create_application_timeline(grouped_emails: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    RULE 7: Create timeline for each application group.
    
    Returns:
        List of application groups with sorted timelines
    """
    timelines = []
    
    for group_key, emails in grouped_emails.items():
        company_name, role_title = group_key.split('||', 1)
        
        # Sort emails by status and date
        sorted_emails = sort_timeline_by_status(emails)
        
        # Group by thread
        threads = group_emails_by_thread(sorted_emails)
        
        timeline = {
            'company_name': company_name,
            'role_title': role_title if role_title else None,
            'emails': sorted_emails,
            'threads': threads,
            'total_emails': len(sorted_emails),
            'total_threads': len(threads),
            'first_email_date': sorted_emails[0].get('received_at') if sorted_emails else None,
            'last_email_date': sorted_emails[-1].get('received_at') if sorted_emails else None,
        }
        
        timelines.append(timeline)
    
    logger.info(f"[THREAD GROUPING] Created {len(timelines)} application timelines")
    
    return timelines
