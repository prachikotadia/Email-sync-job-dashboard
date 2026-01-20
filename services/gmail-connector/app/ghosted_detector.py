"""
Time-based Ghosted Detection (Separate from Model)

STEP 9: "Ghosted" is separate (don't train model for it)
Compute ghosted by time:
- Last status in thread is ACTIVE/INTERVIEW
- No new recruiter/company emails for 30 days
→ set GHOSTED

This is a scheduled job / cron task.
"""

from sqlalchemy.orm import Session
from app.database import Application, User, ClassificationAuditLog
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, List, Dict
import os

logger = logging.getLogger(__name__)


class GhostedDetector:
    """
    Time-based ghosted detection (separate from model classification).
    
    Rules:
    1. Last status in thread is ACTIVE or INTERVIEW
    2. No new recruiter/company emails for N days (default: 30)
    3. → Set GHOSTED
    
    This is NOT part of the model - it's a scheduled job that runs periodically.
    """
    
    def __init__(self, days: int = 30):
        """
        Initialize ghosted detector.
        
        Args:
            days: Number of days of silence before marking as GHOSTED (default: 30)
        """
        self.days = int(os.getenv("GHOSTED_DAYS", str(days)))
    
    def check_all_users(self, db: Session, gmail_client_factory=None):
        """
        Background job to check all users for ghosted applications.
        
        Args:
            db: Database session
            gmail_client_factory: Optional function to create GmailClient for a user
                                 (user_id, user_email, oauth_token) -> GmailClient
        """
        logger.info(f"Starting ghosted detection check (threshold: {self.days} days)")
        
        users = db.query(User).all()
        total_ghosted = 0
        
        for user in users:
            try:
                count = self._check_user(user.id, user.email, db, gmail_client_factory)
                total_ghosted += count
            except Exception as e:
                logger.error(f"Error checking ghosted for user {user.id}: {e}", exc_info=True)
        
        logger.info(f"Ghosted detection check complete. Marked {total_ghosted} applications as GHOSTED")
        return total_ghosted
    
    def _check_user(
        self,
        user_id,
        user_email: str,
        db: Session,
        gmail_client_factory=None
    ) -> int:
        """
        Check and update ghosted applications for a user.
        
        Definition:
        - Last status in thread is ACTIVE or INTERVIEW
        - No new recruiter/company emails for N days
        - → Set GHOSTED
        
        Args:
            user_id: User ID
            user_email: User email
            db: Database session
            gmail_client_factory: Optional function to create GmailClient
        
        Returns:
            Number of applications marked as GHOSTED
        """
        # Get all ACTIVE or INTERVIEW applications (these are candidates for ghosting)
        candidate_apps = db.query(Application).filter(
            Application.user_id == user_id,
            Application.category.in_(["ACTIVE", "INTERVIEW"])
        ).all()
        
        if not candidate_apps:
            return 0
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.days)
        ghosted_count = 0
        
        # Get Gmail client if factory provided (for thread checking)
        gmail_client = None
        if gmail_client_factory:
            try:
                from app.database import OAuthToken
                oauth_token = db.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
                if oauth_token:
                    gmail_client = gmail_client_factory(user_id, user_email, oauth_token)
            except Exception as e:
                logger.debug(f"Could not create Gmail client for user {user_id}: {e}")
        
        for app in candidate_apps:
            try:
                # Check if this application should be marked as GHOSTED
                should_ghost = self._should_mark_ghosted(
                    app,
                    cutoff_date,
                    db,
                    user_email,
                    gmail_client
                )
                
                if should_ghost:
                    old_category = app.category
                    app.category = "GHOSTED"
                    app.last_updated = datetime.now(timezone.utc)
                    app.last_activity_at = datetime.now(timezone.utc)
                    
                    # Create audit log
                    audit_log = ClassificationAuditLog(
                        application_id=app.id,
                        old_status=old_category,
                        new_status="GHOSTED",
                        reason=f"No recruiter/company emails for {self.days} days (time-based ghosting)",
                        classification_source="TIME_BASED",
                        confidence="1.0"
                    )
                    db.add(audit_log)
                    
                    ghosted_count += 1
                    logger.info(
                        f"Marked application {app.id} ({app.company_name}) as GHOSTED "
                        f"(no recruiter emails for {self.days} days, last status: {old_category})"
                    )
            except Exception as e:
                logger.error(f"Error checking ghosted for application {app.id}: {e}", exc_info=True)
                continue
        
        if ghosted_count > 0:
            db.commit()
            logger.info(f"Updated {ghosted_count} applications to GHOSTED for user {user_id}")
        
        return ghosted_count
    
    def _should_mark_ghosted(
        self,
        app: Application,
        cutoff_date: datetime,
        db: Session,
        user_email: str,
        gmail_client=None
    ) -> bool:
        """
        Determine if an application should be marked as GHOSTED.
        
        Rules:
        1. Last status is ACTIVE or INTERVIEW
        2. No new recruiter/company emails in thread for N days
        3. Last activity was before cutoff_date
        
        Args:
            app: Application to check
            cutoff_date: Date threshold (now - N days)
            db: Database session
            user_email: User email (to identify candidate emails)
            gmail_client: Optional GmailClient for thread checking
        
        Returns:
            True if should be marked as GHOSTED
        """
        # Rule 1: Last status must be ACTIVE or INTERVIEW
        if app.category not in ["ACTIVE", "INTERVIEW"]:
            return False
        
        # Rule 2: Check if there are newer emails in the same thread with different status
        # If there's a REJECTED, OFFER, or newer ACTIVE/INTERVIEW, don't ghost
        newer_apps = db.query(Application).filter(
            Application.user_id == app.user_id,
            Application.gmail_thread_id == app.gmail_thread_id,
            Application.received_at > app.received_at,
            Application.category.in_(["REJECTED", "OFFER", "ACTIVE", "INTERVIEW"])
        ).first()
        
        if newer_apps:
            # There's a newer email in the thread - don't ghost
            return False
        
        # Rule 3: Check last activity date
        # Use last_activity_at if available, otherwise received_at
        last_activity = app.last_activity_at or app.received_at
        if not last_activity:
            return False
        
        # Ensure timezone-aware
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        
        # Check if last activity is before cutoff
        if last_activity >= cutoff_date:
            return False
        
        # Rule 4: If Gmail client available, check thread for new recruiter emails
        # This is the most accurate check - verifies no recruiter emails in thread
        if gmail_client and app.gmail_thread_id:
            try:
                has_new_recruiter_email = self._check_thread_for_recruiter_emails(
                    app.gmail_thread_id,
                    last_activity,
                    user_email,
                    gmail_client
                )
                
                if has_new_recruiter_email:
                    # There's a new recruiter email - don't ghost
                    return False
            except Exception as e:
                logger.debug(f"Could not check thread {app.gmail_thread_id} for recruiter emails: {e}")
                # If thread check fails, fall back to time-based check only
        
        # All checks passed - should be marked as GHOSTED
        return True
    
    def _check_thread_for_recruiter_emails(
        self,
        thread_id: str,
        last_activity: datetime,
        user_email: str,
        gmail_client
    ) -> bool:
        """
        Check if there are new recruiter/company emails in the thread after last_activity.
        
        Args:
            thread_id: Gmail thread ID
            last_activity: Last activity timestamp
            user_email: User email (to identify candidate emails)
            gmail_client: GmailClient instance
        
        Returns:
            True if there are new recruiter emails after last_activity
        """
        try:
            thread = gmail_client.get_thread(thread_id)
            if not thread:
                return False
            
            messages = thread.get('messages', [])
            if not messages:
                return False
            
            # Sort messages by date (newest first)
            messages.sort(key=lambda m: int(m.get('internalDate', 0)), reverse=True)
            
            # Check messages after last_activity
            for message in messages:
                internal_date = int(message.get('internalDate', 0))
                if internal_date == 0:
                    continue
                
                message_date = datetime.fromtimestamp(internal_date / 1000, tz=timezone.utc)
                
                # Only check messages after last_activity
                if message_date <= last_activity:
                    break
                
                # Check if this is a recruiter/company email (not candidate email)
                payload = message.get('payload', {})
                headers = payload.get('headers', [])
                
                from_email = None
                for header in headers:
                    if header.get('name', '').lower() == 'from':
                        from_email = header.get('value', '')
                        break
                
                if not from_email:
                    continue
                
                # Extract email address from "Name <email@domain.com>" format
                if '<' in from_email and '>' in from_email:
                    from_email = from_email.split('<')[1].split('>')[0]
                from_email = from_email.strip().lower()
                user_email_lower = user_email.lower()
                
                # Check if this is NOT from the candidate (i.e., from recruiter/company)
                if from_email != user_email_lower and '@' in from_email:
                    # This is a recruiter/company email after last_activity
                    # Don't mark as ghosted
                    logger.debug(
                        f"Found new recruiter email in thread {thread_id} "
                        f"from {from_email} after {last_activity}"
                    )
                    return True
            
            # No new recruiter emails found
            return False
            
        except Exception as e:
            logger.debug(f"Error checking thread for recruiter emails: {e}")
            return False


def create_ghosted_detector() -> GhostedDetector:
    """Factory function to create GhostedDetector with configurable days."""
    days = int(os.getenv("GHOSTED_DAYS", "30"))
    return GhostedDetector(days=days)
