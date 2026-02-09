"""
Advanced Search & Filter System

Unified search endpoint with:
- Global search (company, role, subject, sender_email)
- Multi-select status filter
- Date range filter (date_from, date_to)
- Pagination
- Sorting

All logic is backend-driven for performance with large datasets (1k-50k records).
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, text, case, desc, asc
from typing import List, Dict, Optional
from datetime import datetime, timezone
from app.database import Application, User
from app.gmail_deep_link import build_gmail_deep_link
import logging

logger = logging.getLogger(__name__)


def normalize_company_name(company_name: str) -> str:
    """Normalize company name for consistent searching"""
    if not company_name:
        return ""
    # Lowercase, trim, remove common symbols
    normalized = company_name.lower().strip()
    # Remove common suffixes/prefixes that don't affect search
    normalized = normalized.replace(" inc.", "").replace(" inc", "")
    normalized = normalized.replace(" llc", "").replace(" ltd", "")
    normalized = normalized.replace(" corp", "").replace(" corporation", "")
    return normalized.strip()


def extract_domain_from_email(email: str) -> str:
    """Extract domain from email address"""
    if not email:
        return ""
    if "@" in email:
        return email.split("@")[-1].lower()
    return email.lower()


def advanced_search_applications(
    db: Session,
    user_id: int,
    query: Optional[str] = None,
    status: Optional[List[str]] = None,
    company: Optional[str] = None,
    role: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "received_at",
    sort_order: str = "desc"
) -> Dict:
    """
    Advanced search with filters, pagination, and sorting.
    
    Args:
        db: Database session
        user_id: Database user ID (UUID)
        query: Global search text (searches company, role, subject, sender_email)
        status: List of status values (APPLIED, REJECTED, etc.) - empty means ALL
        date_from: Start date (inclusive) - filters by received_at
        date_to: End date (inclusive) - filters by received_at
        page: Page number (1-indexed)
        page_size: Results per page (max 100)
        sort_by: Field to sort by (received_at, company_name)
        sort_order: Sort direction (asc, desc)
        
    Returns:
        {
            "data": [Application dicts...],
            "pagination": {
                "page": int,
                "page_size": int,
                "total": int,
                "total_pages": int
            }
        }
    """
    # Clamp page_size to reasonable limits
    page_size = min(max(1, page_size), 100)
    page = max(1, page)
    offset = (page - 1) * page_size
    
    # Base query filtered by user
    base_query = db.query(Application).filter(Application.user_id == user_id)
    base_query = base_query.filter(Application.category.notin_(["FILTERED", "IGNORED"]))
    base_query = base_query.filter((Application.is_job_email == True) | (Application.is_job_email.is_(None)))
    
    # Global search query (searches across multiple fields)
    if query and query.strip():
        query_clean = query.strip().lower()
        
        # Build search conditions for:
        # - company_name (exact + partial)
        # - normalized company name (computed: LOWER(TRIM(company_name)))
        # - role
        # - subject (email subject / application title)
        # - application_name (if exists)
        # - sender_email (from_email)
        search_conditions = [
            func.lower(Application.company_name).like(f"%{query_clean}%"),  # Company name
            func.lower(Application.role).like(f"%{query_clean}%") if Application.role else False,  # Role
            func.lower(Application.subject).like(f"%{query_clean}%"),  # Subject/Application title
            func.lower(Application.from_email).like(f"%{query_clean}%") if Application.from_email else False,  # Sender email
        ]
        
        # Add application_name search if column exists (derived field)
        # Check if column exists by trying to add it to search conditions
        try:
            if hasattr(Application, 'application_name') and Application.application_name:
                search_conditions.append(
                    func.lower(Application.application_name).like(f"%{query_clean}%")
                )
        except:
            pass  # Column might not exist yet
        
        # Add normalized company name search (computed on the fly)
        # Use LOWER and TRIM for normalization
        search_conditions.append(
            func.lower(func.trim(Application.company_name)).like(f"%{query_clean}%")
        )
        
        # Also check for domain matching (e.g., "amazon.com" in email)
        if "@" in query_clean or "." in query_clean:
            # If query looks like email/domain, also search in from_email domain
            search_conditions.append(
                func.lower(Application.from_email).like(f"%{query_clean}%")
            )
        
        # Remove False conditions
        search_conditions = [c for c in search_conditions if c is not False]
        
        if search_conditions:
            base_query = base_query.filter(or_(*search_conditions))
    
    # Company filter (exact match - case-insensitive)
    if company:
        # Try company_slug first, fallback to company_name
        base_query = base_query.filter(
            or_(
                func.lower(Application.company_slug) == company.lower().strip(),
                func.lower(Application.company_name) == company.lower().strip()
            )
        )
    
    # Role filter (partial match)
    if role:
        base_query = base_query.filter(func.lower(Application.role).like(f"%{role.lower().strip()}%"))
    
    # Multi-select status filter
    if status and len(status) > 0:
        # Normalize status values (uppercase, handle OFFER/ACCEPTED → OFFER_ACCEPTED, APPLIED → ACTIVE)
        normalized_statuses = []
        for s in status:
            s_upper = s.upper().strip()
            if s_upper in ("OFFER", "ACCEPTED"):
                s_upper = "OFFER_ACCEPTED"
            elif s_upper == "APPLIED":
                # Map APPLIED to ACTIVE (dashboard compatibility - ACTIVE is the actual DB category)
                s_upper = "ACTIVE"
            normalized_statuses.append(s_upper)
        
        if normalized_statuses:
            base_query = base_query.filter(Application.category.in_(normalized_statuses))
    
    # Date range filter (applied to received_at, which serves as applied_at)
    # Only apply filters if dates are provided (None means no filter - show all)
    if date_from is not None:
        # Ensure timezone-aware
        if date_from.tzinfo is None:
            date_from = date_from.replace(tzinfo=timezone.utc)
        base_query = base_query.filter(Application.received_at >= date_from)
    
    if date_to is not None:
        # Ensure timezone-aware and include the full day
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=timezone.utc)
        # Add 1 day to include the entire end date
        date_to_end = date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
        base_query = base_query.filter(Application.received_at <= date_to_end)
    
    # Get total count (before pagination)
    total = base_query.count()
    
    # Sorting - default to last_activity_at if available, fallback to received_at
    if sort_by == "company_name":
        order_field = Application.company_name
    elif sort_by == "last_activity_at":
        # Use last_activity_at if available, fallback to received_at
        order_field = Application.last_activity_at if hasattr(Application, 'last_activity_at') else Application.received_at
    elif sort_by == "received_at":
        order_field = Application.received_at
    else:
        # Default: try last_activity_at first, then received_at
        try:
            order_field = Application.last_activity_at if hasattr(Application, 'last_activity_at') else Application.received_at
        except:
            order_field = Application.received_at
    
    # Apply sort order
    if sort_order.lower() == "asc":
        base_query = base_query.order_by(asc(order_field))
    else:
        base_query = base_query.order_by(desc(order_field))
    
    # Apply pagination
    results = base_query.offset(offset).limit(page_size).all()
    
    # Format results
    formatted_results = []
    for app in results:
        # Normalize category
        category = app.category.upper() if app.category else "APPLIED"
        if category in ("ACCEPTED", "OFFER"):
            category = "OFFER_ACCEPTED"
        elif category == "ACTIVE":
            # Map ACTIVE to APPLIED for frontend compatibility (dashboard shows ACTIVE as APPLIED)
            category = "APPLIED"
        
        # Generate Gmail deep link using message ID
        if not app.gmail_message_id:
            logger.warning(f"Application {app.id} missing gmail_message_id - cannot generate deep link")
            gmail_deep_link = None
            gmail_web_url = None
        else:
            gmail_deep_link = build_gmail_deep_link(app.gmail_message_id)
            gmail_web_url = gmail_deep_link  # Legacy field
        
        formatted_results.append({
            "id": str(app.id),
            "company_name": app.company_name or "Unknown Company",
            "normalized_company_name": normalize_company_name(app.company_name),
            "role": app.role,
            "application_title": app.subject or "No Subject",  # subject serves as application_title
            "email_subject": app.subject or "No Subject",
            "sender_email": app.from_email,
            "sender_domain": extract_domain_from_email(app.from_email) if app.from_email else None,
            "status": category,
            "category": category,  # Add category field for frontend compatibility
            "applied_at": app.received_at.isoformat() if app.received_at else None,  # received_at serves as applied_at
            "received_at": app.received_at.isoformat() if app.received_at else None,
            "email_message_id": app.gmail_message_id,
            "gmail_message_id": app.gmail_message_id,  # Explicit field
            "gmail_deep_link": gmail_deep_link,  # Primary field (new)
            "gmail_web_url": gmail_web_url,  # Legacy field (backward compatibility)
            "snippet": app.snippet,
        })
    
    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    return {
        "data": formatted_results,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }
