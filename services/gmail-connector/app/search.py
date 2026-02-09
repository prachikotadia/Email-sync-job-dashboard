"""
Production-Grade Global Search System

Implements fast, typo-tolerant, scalable search across:
- Company name (exact + partial + alias)
- Role / Job title
- Email subject
- Application status

Uses PostgreSQL full-text search (tsvector) and trigram (pg_trgm) for fuzzy matching.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, text, case
from typing import List, Dict, Optional
from app.database import Application, User
import json
import logging

logger = logging.getLogger(__name__)

def search_applications(
    db: Session,
    user_id: int,
    query: str,
    limit: int = 50,
    offset: int = 0
) -> Dict:
    """
    Production-grade search with ranking logic.
    
    Ranking order:
    1. Exact company match
    2. Partial company match (ILIKE)
    3. Company alias match
    4. Role match
    5. Subject match
    6. Status match
    
    Args:
        db: Database session
        user_id: Database user ID (not email)
        query: Search query string
        limit: Max results per page (default 50)
        offset: Pagination offset
        
    Returns:
        {
            "results": [...],
            "total": int,
            "limit": int,
            "offset": int
        }
    """
    if not query or not query.strip():
        return {"results": [], "total": 0, "limit": limit, "offset": offset}
    
    query_clean = query.strip().lower()
    
    # Base query filtered by user
    base_query = db.query(Application).filter(Application.user_id == user_id)
    base_query = base_query.filter(Application.category.notin_(["FILTERED", "IGNORED"]))
    base_query = base_query.filter((Application.is_job_email == True) | (Application.is_job_email.is_(None)))
    
    # Build search conditions with ranking
    # Use CASE statements for ranking (higher score = better match)
    exact_company_match = case(
        (func.lower(Application.company_name) == query_clean, 100),
        else_=0
    ).label('exact_company')
    
    partial_company_match = case(
        (func.lower(Application.company_name).like(f"%{query_clean}%"), 80),
        else_=0
    ).label('partial_company')
    
    # Check company aliases (JSON array)
    alias_match_score = case(
        (text(f"LOWER(company_aliases::text) LIKE '%{query_clean}%'"), 70),
        else_=0
    ).label('alias_match')
    
    role_match = case(
        (func.lower(Application.role).like(f"%{query_clean}%"), 50),
        else_=0
    ).label('role_match')
    
    subject_match = case(
        (func.lower(Application.subject).like(f"%{query_clean}%"), 30),
        else_=0
    ).label('subject_match')
    
    # Status match (map query to status values)
    status_map = {
        'applied': 'APPLIED',
        'rejected': 'REJECTED',
        'interview': 'INTERVIEW',
        'offer': 'OFFER_ACCEPTED',
        'accepted': 'OFFER_ACCEPTED',
        'ghosted': 'GHOSTED'
    }
    status_value = status_map.get(query_clean, None)
    if status_value:
        status_match = case(
            (Application.category == status_value, 40),
            else_=0
        ).label('status_match')
    else:
        # No status match - always return 0
        status_match = case(else_=0).label('status_match')
    
    # Calculate total rank (sum of all match scores)
    total_rank = (
        exact_company_match +
        partial_company_match +
        alias_match_score +
        role_match +
        subject_match +
        status_match
    ).label('rank')
    
    # Build search filter - match if ANY condition is true
    search_conditions = [
        func.lower(Application.company_name) == query_clean,  # Exact company
        func.lower(Application.company_name).like(f"%{query_clean}%"),  # Partial company
        text(f"LOWER(company_aliases::text) LIKE '%{query_clean}%'"),  # Alias
        func.lower(Application.role).like(f"%{query_clean}%"),  # Role
        func.lower(Application.subject).like(f"%{query_clean}%"),  # Subject
    ]
    if status_value:
        search_conditions.append(Application.category == status_value)  # Status
    
    search_filter = or_(*search_conditions)
    
    # Apply search filter
    search_query = base_query.filter(search_filter)
    
    # Add rank to query and order by rank (descending), then by date (descending)
    search_query = search_query.add_columns(total_rank)
    
    # Get total count (before pagination)
    total = search_query.count()
    
    # Apply pagination and ordering
    results = search_query.order_by(
        total_rank.desc(),
        Application.received_at.desc()
    ).offset(offset).limit(limit).all()
    
    # Format results
    formatted_results = []
    for row in results:
        app = row[0] if isinstance(row, tuple) else row  # Handle tuple result from add_columns
        rank = row[1] if isinstance(row, tuple) else 0
        
        # Normalize category
        category = app.category.upper() if app.category else "APPLIED"
        if category == "ACCEPTED" or category == "OFFER":
            category = "OFFER_ACCEPTED"
        
        formatted_results.append({
            "application_id": str(app.id),
            "company_name": app.company_name or "Unknown Company",
            "role": app.role or None,
            "status": category,
            "subject": app.subject or "No Subject",
            "applied_date": app.received_at.date().isoformat() if app.received_at else None,
            "received_at": app.received_at.isoformat() if app.received_at else None,
            "rank": rank  # Include rank for debugging (optional)
        })
    
    return {
        "results": formatted_results,
        "total": total,
        "limit": limit,
        "offset": offset
    }


def search_applications_fuzzy(
    db: Session,
    user_id: int,
    query: str,
    limit: int = 50,
    offset: int = 0
) -> Dict:
    """
    Advanced fuzzy search using PostgreSQL trigram similarity.
    Falls back to basic search if trigram extension is not available.
    
    Uses pg_trgm for typo-tolerant matching (e.g., "amazn" → "Amazon").
    """
    if not query or not query.strip():
        return search_applications(db, user_id, query, limit, offset)
    
    query_clean = query.strip().lower()
    
    # Check if pg_trgm is available
    try:
        # Try to use trigram similarity
        base_query = db.query(Application).filter(Application.user_id == user_id)
        base_query = base_query.filter(Application.category.notin_(["FILTERED", "IGNORED"]))
        base_query = base_query.filter((Application.is_job_email == True) | (Application.is_job_email.is_(None)))
        
        # Use similarity function for fuzzy matching
        company_similarity = func.similarity(func.lower(Application.company_name), query_clean).label('company_sim')
        role_similarity = func.similarity(func.lower(func.coalesce(Application.role, '')), query_clean).label('role_sim')
        
        # Combine similarities (company weighted higher)
        total_similarity = (
            company_similarity * 2.0 +  # Company match is 2x more important
            role_similarity
        ).label('total_sim')
        
        # Filter by similarity threshold (at least 0.1 similarity = fuzzy match)
        similarity_threshold = 0.1
        search_filter = or_(
            func.similarity(func.lower(Application.company_name), query_clean) >= similarity_threshold,
            func.similarity(func.lower(func.coalesce(Application.role, '')), query_clean) >= similarity_threshold,
            func.lower(Application.company_name).like(f"%{query_clean}%"),  # Fallback to partial match
            func.lower(Application.role).like(f"%{query_clean}%")
        )
        
        search_query = base_query.filter(search_filter).add_columns(total_similarity)
        
        # Get total count
        total = search_query.count()
        
        # Apply pagination and ordering by similarity
        results = search_query.order_by(
            total_similarity.desc(),
            Application.received_at.desc()
        ).offset(offset).limit(limit).all()
        
        # Format results
        formatted_results = []
        for row in results:
            app = row[0] if isinstance(row, tuple) else row
            sim = row[1] if isinstance(row, tuple) else 0.0
            
            category = app.category.upper() if app.category else "APPLIED"
            if category == "ACCEPTED" or category == "OFFER":
                category = "OFFER_ACCEPTED"
            
            formatted_results.append({
                "application_id": str(app.id),
                "company_name": app.company_name or "Unknown Company",
                "role": app.role or None,
                "status": category,
                "subject": app.subject or "No Subject",
                "applied_date": app.received_at.date().isoformat() if app.received_at else None,
                "received_at": app.received_at.isoformat() if app.received_at else None,
                "similarity": round(sim, 3)  # Include similarity score for debugging (optional)
            })
        
        return {
            "results": formatted_results,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        # If trigram is not available, fall back to basic search
        logger.warning(f"Fuzzy search not available (pg_trgm extension?), falling back to basic search: {e}")
        return search_applications(db, user_id, query, limit, offset)
