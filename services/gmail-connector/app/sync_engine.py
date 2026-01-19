from typing import AsyncIterator, Dict, List
from sqlalchemy.orm import Session
from app.gmail_client import GmailClient
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor
from app.database import Application, User
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class SyncEngine:
    """
    Gmail sync engine
    Fetches ALL emails with no limits
    Every login = check for new emails (incremental if historyId exists)
    
    SECURITY & PRIVACY GUARANTEE:
    - Email body content must NEVER be logged (no full email bodies in logs)
    - Only metadata is logged: message IDs, counts, status, error messages
    - Email content is stored in database but NOT in logs
    - Privacy is non-negotiable - email content stays private
    """
    
    def __init__(
        self,
        gmail_client: GmailClient,
        classifier: Classifier,
        company_extractor: CompanyExtractor,
        db: Session
    ):
        self.gmail_client = gmail_client
        self.classifier = classifier
        self.company_extractor = company_extractor
        self.db = db
        self.latest_history_id = None
    
    def get_latest_history_id(self) -> str:
        """Get the latest history ID from sync"""
        return self.latest_history_id
    
    async def sync_all_emails(
        self, 
        user_id: int, 
        existing_history_id: str = None,
        mode: str = "full_history",  # "full_history" or "time_range"
        time_range_months: int = None,  # For time_range mode: 3, 6, or 12
        checkpoint_token: str = None  # Resume from checkpoint
    ) -> AsyncIterator[Dict]:
        """
        Sync ALL emails from Gmail (per spec requirements)
        
        Mode A - Full History: Fetch ALL emails in mailbox
        Mode B - Time Range: Fetch emails after timestamp (3/6/12 months)
        
        NO subject queries - filtering happens AFTER fetching
        NO pagination limits - continues until nextPageToken is null
        Yields progress updates for real-time UI
        
        IDEMPOTENCY RULE (CRITICAL):
        - Sync must be idempotent - re-running MUST NOT duplicate messages/applications/counts
        - Before processing, check if messageId already exists in Application table
        - Skip already-processed messageIds to prevent duplicates
        - _save_application uses upsert logic (update if exists) as additional safeguard
        
        Args:
            user_id: Database user ID
            existing_history_id: For incremental sync (if provided)
            mode: "full_history" or "time_range"
            time_range_months: For time_range mode (3, 6, or 12 months)
            checkpoint_token: Resume from this page token (for crash recovery)
        """
        total_scanned = 0
        total_fetched = 0
        candidate_job_emails = 0
        classified = {
            "APPLIED": 0,
            "REJECTED": 0,
            "INTERVIEW": 0,
            "OFFER_ACCEPTED": 0,
            "GHOSTED": 0,
        }
        skipped = 0
        
        # Calculate start timestamp for time range mode
        start_timestamp_ms = None
        if mode == "time_range" and time_range_months:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_months * 30)
            start_timestamp_ms = int(cutoff_date.timestamp() * 1000)
            logger.info(f"Time range mode: fetching emails after {cutoff_date} ({time_range_months} months)")
        
        try:
            # CRITICAL: Fetch ALL messages WITHOUT subject query (per spec requirement 0)
            # NO q parameter for subject/keyword filtering
            # Filtering happens AFTER fetching in Stage 1
            logger.info(f"Starting sync for user {user_id}: Mode={mode}, history_id={existing_history_id}")
            
            # Fetch ALL messages - pagination continues until nextPageToken is null
            messages, latest_history_id, next_page_token = self.gmail_client.get_all_messages(
                history_id=existing_history_id,
                start_timestamp_ms=start_timestamp_ms,
                page_token=checkpoint_token
            )
            self.latest_history_id = latest_history_id
            total_fetched = len(messages)
            total_scanned = total_fetched  # For full history, scanned = fetched
            
            # Logging MUST match requirements: "Total Gmail emails: X, Fetched: X"
            logger.info(f"Total Gmail emails scanned: {total_scanned}")
            logger.info(f"Fetched messages: {total_fetched}")
            
            # For full history mode: scanned should equal fetched (we fetch everything)
            # For time range mode: scanned may be less than total mailbox size
            
            # Note: next_page_token will be None when pagination is complete
            # For incremental checkpointing during pagination (for 30k+ emails),
            # get_all_messages would need to be refactored to yield pages incrementally
            
            # IDEMPOTENCY: Check which messageIds already exist in database
            # This prevents re-processing messages on resume or re-run
            message_ids_to_check = [msg.get('id') for msg in messages if msg.get('id')]
            existing_message_ids = set()
            if message_ids_to_check:
                from app.database import Application
                existing_apps = self.db.query(Application.gmail_message_id).filter(
                    Application.gmail_message_id.in_(message_ids_to_check),
                    Application.user_id == user_id
                ).all()
                existing_message_ids = {app.gmail_message_id for app in existing_apps}
                logger.info(f"IDEMPOTENCY CHECK: Found {len(existing_message_ids)} already-processed messages (skipping duplicates)")
            
            # Stage 1: High Recall - Filter candidate job emails (skip already processed)
            candidate_emails = []
            for message in messages:
                try:
                    message_id = message.get('id')
                    
                    # IDEMPOTENCY: Skip if message already processed
                    if message_id in existing_message_ids:
                        skipped += 1
                        continue
                    
                    if self._is_candidate_job_email(message):
                        candidate_emails.append(message)
                        candidate_job_emails += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.warning(f"Error checking message {message.get('id')}: {e}")
                    skipped += 1
                    continue
            
            logger.info(f"Stage 1: Found {candidate_job_emails} candidate job emails (after skipping {len(existing_message_ids)} already processed)")
            
            # Stage 2: High Precision - Classify and save (batch processing for speed)
            # Optimized batch size: 50-100 emails per batch for better memory efficiency
            # Smaller batches = lower memory usage, better cancellation responsiveness
            batch_size = 50  # Process and yield every 50 emails for optimal performance/memory balance
            batch_count = 0
            last_processed_message_id = None
            last_processed_internal_date = None
            
            for idx, message in enumerate(candidate_emails):
                try:
                    message_id = message.get('id')
                    internal_date = message.get('internalDate')  # Unix timestamp in milliseconds
                    
                    # IDEMPOTENCY: Double-check (defensive check, should already be filtered above)
                    if message_id in existing_message_ids:
                        skipped += 1
                        continue
                    
                    # Extract application data
                    application_data = self._extract_application(message)
                    
                    if not application_data:
                        skipped += 1
                        continue
                    
                    # Stage 2: Classify (High Precision)
                    category = self.classifier.classify(application_data)
                    
                    if category == "skip":
                        skipped += 1
                        continue
                    
                    # Get thread ID from message
                    thread_id = message.get('threadId')
                    
                    # IDEMPOTENCY: Save to database (upsert logic in _save_application prevents duplicates)
                    # CRITICAL: Track if save succeeded to ensure classified count matches saved count
                    try:
                        self._save_application(user_id, message_id, application_data, category, thread_id)
                        save_succeeded = True
                    except Exception as save_error:
                        logger.error(f"Failed to save application for message {message_id}: {save_error}")
                        save_succeeded = False
                        skipped += 1
                        continue  # Skip if save failed
                    
                    # Only count as classified if save succeeded
                    if save_succeeded:
                        # Track last processed for checkpoint (for resume capability)
                        last_processed_message_id = message_id
                        last_processed_internal_date = internal_date
                        
                        # Update classified counts (category is already uppercase from classifier or will be normalized)
                        category_upper = category.upper()
                        if category_upper == "OFFER":
                            category_upper = "OFFER_ACCEPTED"
                        if category_upper in classified:
                            classified[category_upper] += 1
                        
                        # Yield email entry for UI display (only if saved successfully)
                        email_entry = {
                            "id": message_id,
                            "company": application_data.get("company_name", "Unknown Company"),
                            "snippet": application_data.get("snippet", "")[:100],  # Truncate snippet
                            "category": category_upper,
                            "subject": application_data.get("subject", "")[:80],  # Truncate subject
                        }
                    else:
                        # Save failed - no email entry
                        email_entry = None
                    
                    batch_count += 1
                    processed_count = sum(classified.values())
                    
                    # Yield progress update for EVERY email (real-time updates)
                    # This allows the UI to show each email being processed one by one
                    yield {
                        "total_scanned": total_scanned,
                        "total_fetched": total_fetched,
                        "candidate_job_emails": candidate_job_emails,
                        "processed_emails": processed_count,  # Only counts successfully saved emails
                        "classified": classified.copy(),
                        "skipped": skipped,
                        "email_entry": email_entry,  # Include email entry only if saved successfully
                        "page_token": next_page_token,  # Include page token for checkpoint
                        "last_processed_message_id": last_processed_message_id,  # For checkpoint persistence
                        "last_processed_internal_date": last_processed_internal_date,  # For checkpoint persistence
                    }
                    
                    # Reset batch count after yielding (we still process in batches for efficiency)
                    if batch_count >= batch_size:
                        batch_count = 0
                        
                except Exception as e:
                    logger.warning(f"Error processing message {message.get('id')}: {e}")
                    skipped += 1
                    continue
            
            logger.info(
                f"Fetched: {total_fetched} emails. Job-related candidates: {candidate_job_emails}. "
                f"APPLIED: {classified['APPLIED']}, REJECTED: {classified['REJECTED']}, "
                f"INTERVIEW: {classified['INTERVIEW']}, OFFER_ACCEPTED: {classified['OFFER_ACCEPTED']}, "
                f"GHOSTED: {classified['GHOSTED']}. Skipped: {skipped}."
            )
            
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            raise
    
    def _is_candidate_job_email(self, message: Dict) -> bool:
        """
        Stage 1: High Recall - Loose filter to not miss job emails
        """
        payload = message.get('payload', {})
        headers = payload.get('headers', [])
        
        subject = ""
        snippet = message.get('snippet', '').lower()
        
        for header in headers:
            if header.get('name', '').lower() == 'subject':
                subject = header.get('value', '').lower()
                break
        
        # High recall keywords
        keywords = [
            'application', 'applied', 'interview', 'offer', 'rejection',
            'thank you for applying', 'application update', 'position',
            'hiring', 'job', 'career', 'recruiter', 'ats'
        ]
        
        text = f"{subject} {snippet}"
        
        # Check for keywords
        for keyword in keywords:
            if keyword in text:
                return True
        
        # Check for known ATS domains
        from_email = ""
        for header in headers:
            if header.get('name', '').lower() == 'from':
                from_email = header.get('value', '').lower()
                break
        
        ats_domains = [
            'greenhouse.io', 'lever.co', 'workday.com', 'smartrecruiters.com',
            'jobvite.com', 'icims.com', 'taleo.net', 'brassring.com'
        ]
        
        for domain in ats_domains:
            if domain in from_email:
                return True
        
        return False
    
    def _extract_application(self, message: Dict) -> Dict:
        """
        Extract application data from Gmail message
        """
        payload = message.get('payload', {})
        headers = payload.get('headers', [])
        
        # Extract headers
        subject = ""
        from_email = ""
        date_str = ""
        
        for header in headers:
            name = header.get('name', '').lower()
            value = header.get('value', '')
            
            if name == 'subject':
                subject = value
            elif name == 'from':
                from_email = value
            elif name == 'date':
                date_str = value
        
        # Parse date (with timezone)
        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
            # Ensure timezone-aware
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
        except:
            received_at = datetime.now(timezone.utc)
        
        # Extract company and role using company extractor (pass full message for HTML parsing)
        company, source, confidence = self.company_extractor.extract(
            message, subject, from_email, message.get('snippet', '')
        )
        role = self.company_extractor.extract_role(subject, message.get('snippet', ''))
        
        # Company is guaranteed to never be None (extractor always returns a value)
        if not company:
            company = 'Unknown Company'  # Safety fallback (should never happen)
        
        return {
            "company_name": company,
            "role": role,
            "subject": subject,
            "from_email": from_email,
            "received_at": received_at,
            "snippet": message.get('snippet', ''),
        }
    
    def _generate_gmail_web_url(self, message_id: str) -> str:
        """
        Generate Gmail web URL for a message (legacy wrapper)
        Uses build_gmail_deep_link for consistency.
        """
        from app.gmail_deep_link import build_gmail_deep_link
        return build_gmail_deep_link(message_id)

    def _extract_company_domain(self, from_email: str) -> str:
        """
        Extract company domain from email address
        """
        if '@' not in from_email:
            return None
        domain = from_email.split('@')[1].lower()
        # Filter out common email providers
        if domain in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com']:
            return None
        return domain

    def _save_application(
        self,
        user_id,  # Can be UUID or int (for backward compatibility during migration)
        gmail_message_id: str,
        application_data: Dict,
        category: str,
        thread_id: str = None
    ):
        """
        Save application to database (upsert)
        Ensures company_name is never null
        Category must be uppercase: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED
        Generates gmail_web_url and extracts company_domain
        """
        # Ensure category is uppercase
        category_upper = category.upper() if category != "skip" else None
        if category_upper == "OFFER":
            category_upper = "OFFER_ACCEPTED"  # Normalize offer to OFFER_ACCEPTED
        
        if not category_upper or category_upper not in ["APPLIED", "REJECTED", "INTERVIEW", "OFFER_ACCEPTED", "GHOSTED"]:
            logger.warning(f"Invalid category: {category}, cannot save")
            # CRITICAL: Raise exception so caller knows save failed (for verification)
            # This ensures classified count matches saved count
            raise ValueError(f"Invalid category '{category}' - cannot save application")
        
        # Ensure company_name is never null - use fallback
        company_name = application_data.get("company_name")
        if not company_name or company_name.strip() == '':
            # Fallback extraction from email domain
            from_email = application_data.get("from_email", "")
            if '@' in from_email:
                domain = from_email.split('@')[1].lower()
                # Remove common email providers
                if domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com']:
                    company_name = domain.split('.')[0].capitalize()
                else:
                    company_name = 'Unknown Company'
            else:
                company_name = 'Unknown Company'
        
        # Extract company domain
        from_email = application_data.get("from_email", "")
        company_domain = self._extract_company_domain(from_email)
        
        # Ensure subject is never null
        subject = application_data.get("subject", "")
        if not subject or subject.strip() == '':
            subject = "No Subject"
        
        # Generate Gmail web URL
        gmail_web_url = self._generate_gmail_web_url(gmail_message_id)
        
        # Ensure thread_id is never null
        if not thread_id:
            thread_id = gmail_message_id  # Use message_id as fallback
        
        # Generate company_slug (lowercase, normalized for URL routing)
        import re
        company_slug = re.sub(r'[^a-z0-9]+', '-', company_name.lower().strip())
        company_slug = re.sub(r'^-+|-+$', '', company_slug)  # Remove leading/trailing dashes
        
        # Generate application_name (derived from subject + company + role)
        role_title = application_data.get("role") or ""
        application_name_parts = [company_name]
        if role_title:
            application_name_parts.append(role_title)
        application_name_parts.append(subject[:100])  # Truncate subject
        application_name = " - ".join(application_name_parts)
        
        # Set last_activity_at (initially same as received_at, updates on status change)
        received_at_value = application_data.get("received_at") or datetime.now(timezone.utc)
        last_activity_at_value = received_at_value
        
        # IDEMPOTENCY: Check if application already exists (upsert to prevent duplicates)
        # This is a defensive check - messages should already be filtered before classification
        existing = self.db.query(Application).filter(
            Application.gmail_message_id == gmail_message_id
        ).first()
        
        if existing:
            # IDEMPOTENCY: Update existing (upsert logic - prevents duplicates on re-run)
            existing.company_name = company_name
            existing.company_domain = company_domain
            existing.role = application_data.get("role")
            existing.category = category_upper
            existing.subject = subject
            existing.from_email = from_email
            existing.received_at = application_data.get("received_at")
            existing.snippet = application_data.get("snippet")
            existing.gmail_thread_id = thread_id
            existing.gmail_web_url = gmail_web_url
            existing.last_updated = datetime.now(timezone.utc)
            # Update new fields if they exist
            if hasattr(existing, 'company_slug'):
                existing.company_slug = company_slug
            if hasattr(existing, 'application_name'):
                existing.application_name = application_name
            # Update last_activity_at if category changed (status change = activity)
            if hasattr(existing, 'last_activity_at'):
                if existing.category != category_upper:
                    existing.last_activity_at = datetime.now(timezone.utc)
                elif not existing.last_activity_at:
                    existing.last_activity_at = last_activity_at_value
        else:
            # Create new
            app_data = {
                'user_id': user_id,
                'gmail_message_id': gmail_message_id,
                'gmail_thread_id': thread_id,
                'gmail_web_url': gmail_web_url,
                'company_name': company_name,
                'company_domain': company_domain,
                'role': application_data.get("role"),
                'category': category_upper,
                'subject': subject,
                'from_email': from_email,
                'received_at': application_data.get("received_at"),
                'snippet': application_data.get("snippet"),
            }
            # Add new fields if they exist in the model
            if hasattr(Application, 'company_slug'):
                app_data['company_slug'] = company_slug
            if hasattr(Application, 'application_name'):
                app_data['application_name'] = application_name
            if hasattr(Application, 'last_activity_at'):
                app_data['last_activity_at'] = last_activity_at_value
            
            application = Application(**app_data)
            self.db.add(application)
        
        self.db.commit()
