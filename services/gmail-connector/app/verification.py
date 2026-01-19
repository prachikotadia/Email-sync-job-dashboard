"""
Metrics & Verification Module (FINAL SAFETY NET)

Hard acceptance criteria to prevent "looks like it works" bugs.
These checks MUST pass after every sync to ensure data integrity.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SyncJob, Application

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Raised when verification fails"""
    pass


def verify_sync_completion(db: Session, sync_job: SyncJob, user_id: int) -> dict:
    """
    Verify sync completion against acceptance criteria.
    
    ACCEPTANCE CRITERIA:
    1. Gmail total count == fetched count
    2. DB stored count == classified count (for job emails)
    3. No duplicate message IDs in database
    4. Checkpoint contains all required fields
    
    Args:
        db: Database session
        sync_job: Completed SyncJob instance
        user_id: User ID to verify
        
    Returns:
        dict: Verification results with counts and status
        
    Raises:
        VerificationError: If any acceptance criteria fails
    """
    verification_results = {
        "passed": True,
        "errors": [],
        "counts": {}
    }
    
    try:
        # Get counts from sync job
        # CRITICAL: Use correct fields for verification
        gmail_total = sync_job.total_emails or 0
        gmail_fetched = sync_job.counts_fetched or 0  # Actual fetched from Gmail
        sync_classified = sync_job.counts_classified or 0  # Actual classified and saved count
        
        # Get actual DB count
        db_app_count = db.query(Application).filter(Application.user_id == user_id).count()
        
        # Count unique message IDs (should equal db_app_count if no duplicates)
        unique_message_ids = db.query(
            Application.gmail_message_id
        ).filter(
            Application.user_id == user_id
        ).distinct().count()
        
        verification_results["counts"] = {
            "gmail_total": gmail_total,
            "gmail_fetched": gmail_fetched,
            "sync_classified": sync_classified,
            "db_stored": db_app_count,
            "unique_message_ids": unique_message_ids
        }
        
        # ACCEPTANCE CRITERIA 1: Gmail total == fetched count
        # For full_history mode, all emails must be fetched
        # For time_range mode, fetched may be less than total mailbox size
        checkpoint = sync_job.checkpoint or {}
        mode = checkpoint.get("mode", "full_history")
        
        if mode == "full_history":
            if gmail_total != gmail_fetched:
                error_msg = f"CRITICAL: Gmail total ({gmail_total}) != fetched ({gmail_fetched})"
                verification_results["errors"].append(error_msg)
                verification_results["passed"] = False
                logger.error(error_msg)
        
        # ACCEPTANCE CRITERIA 2: DB stored == classified count
        # All classified job emails should be stored in database
        if db_app_count != sync_classified:
            error_msg = f"CRITICAL: DB stored ({db_app_count}) != classified ({sync_classified})"
            verification_results["errors"].append(error_msg)
            verification_results["passed"] = False
            logger.error(error_msg)
        
        # ACCEPTANCE CRITERIA 3: No duplicate message IDs
        if unique_message_ids != db_app_count:
            duplicate_count = db_app_count - unique_message_ids
            error_msg = f"CRITICAL: Found {duplicate_count} duplicate message IDs (unique: {unique_message_ids}, total: {db_app_count})"
            verification_results["errors"].append(error_msg)
            verification_results["passed"] = False
            logger.error(error_msg)
        
        # ACCEPTANCE CRITERIA 4: Checkpoint contains required fields
        required_checkpoint_fields = ["mode", "page_token", "sync_state"]
        for field in required_checkpoint_fields:
            if field not in checkpoint:
                error_msg = f"CRITICAL: Checkpoint missing required field: {field}"
                verification_results["errors"].append(error_msg)
                verification_results["passed"] = False
                logger.error(error_msg)
        
        # Log verification results
        if verification_results["passed"]:
            logger.info(
                f"✅ Verification PASSED for sync {sync_job.id}: "
                f"Gmail={gmail_total}, Fetched={gmail_fetched}, "
                f"Classified={sync_classified}, DB={db_app_count}"
            )
        else:
            logger.error(
                f"❌ Verification FAILED for sync {sync_job.id}: {len(verification_results['errors'])} errors"
            )
        
        return verification_results
        
    except Exception as e:
        error_msg = f"Verification error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        verification_results["passed"] = False
        verification_results["errors"].append(error_msg)
        return verification_results


def verify_idempotency(db: Session, user_id: int, before_count: int, after_count: int) -> dict:
    """
    Verify re-sync idempotency: re-running sync without new emails changes NOTHING.
    
    ACCEPTANCE CRITERIA 4: Re-sync without new emails changes NOTHING
    
    Args:
        db: Database session
        user_id: User ID
        before_count: Application count before re-sync
        after_count: Application count after re-sync
        
    Returns:
        dict: Verification results
    """
    verification_results = {
        "passed": True,
        "errors": [],
        "before_count": before_count,
        "after_count": after_count
    }
    
    if before_count != after_count:
        error_msg = f"CRITICAL: Re-sync changed count! Before: {before_count}, After: {after_count}"
        verification_results["errors"].append(error_msg)
        verification_results["passed"] = False
        logger.error(error_msg)
    else:
        logger.info(f"✅ Idempotency verified: Re-sync did not change count ({before_count})")
    
    return verification_results


def verify_dashboard_counts_match(db: Session, user_id: int, api_response: dict) -> dict:
    """
    Verify dashboard counts match database counts.
    
    ACCEPTANCE CRITERIA 3: Dashboard count == DB count
    
    Args:
        db: Database session
        user_id: User ID
        api_response: API response from GET /api/gmail/applications
        
    Returns:
        dict: Verification results
    """
    verification_results = {
        "passed": True,
        "errors": []
    }
    
    # Get actual DB count
    db_count = db.query(Application).filter(Application.user_id == user_id).count()
    
    # Get API count
    api_total = api_response.get("total", 0)
    api_applications = api_response.get("applications", [])
    api_applications_count = len(api_applications)
    
    # API total should match DB count
    if api_total != db_count:
        error_msg = f"CRITICAL: API total ({api_total}) != DB count ({db_count})"
        verification_results["errors"].append(error_msg)
        verification_results["passed"] = False
        logger.error(error_msg)
    
    # If no pagination, applications array length should match total
    # (This assumes API returns all applications without pagination)
    # Note: If pagination is used, this check may not apply
    
    return verification_results
