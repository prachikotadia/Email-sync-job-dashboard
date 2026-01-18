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
    
    async def sync_all_emails(self, user_id: int, existing_history_id: str = None) -> AsyncIterator[Dict]:
        """
        Sync ALL emails from Gmail
        NO pagination limits
        Uses incremental sync if historyId exists
        Yields progress updates
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
        
        # Query for job-related emails (Stage 1 - High Recall)
        # Use broad query to catch ALL potential job emails
        query = "subject:(application OR applied OR interview OR offer OR rejection OR thank you OR hiring OR position)"
        
        try:
            # Get total count first (estimate from Gmail API)
            total_count = self.gmail_client.get_message_count(query)
            total_scanned = total_count
            
            logger.info(f"Starting sync for user {user_id}: Estimated {total_count} emails to scan")
            
            # Fetch ALL messages (incremental if historyId exists)
            # This MUST paginate until nextPageToken is null - NO early exit
            messages, latest_history_id = self.gmail_client.get_all_messages(query, existing_history_id)
            self.latest_history_id = latest_history_id
            total_fetched = len(messages)
            
            # Logging MUST match requirements: "Total Gmail emails: X, Fetched: X"
            logger.info(f"Total Gmail emails: {total_scanned}")
            logger.info(f"Fetched messages: {total_fetched}")
            
            # Verify: If X ≠ X → BUG (but allow for API estimate vs actual)
            if total_fetched < total_scanned * 0.9:  # Allow 10% variance for API estimates
                logger.warning(f"Fetched count ({total_fetched}) significantly less than estimated ({total_scanned}). May indicate pagination issue.")
            
            # Stage 1: High Recall - Filter candidate job emails
            candidate_emails = []
            for message in messages:
                try:
                    if self._is_candidate_job_email(message):
                        candidate_emails.append(message)
                        candidate_job_emails += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.warning(f"Error checking message {message.get('id')}: {e}")
                    skipped += 1
                    continue
            
            logger.info(f"Stage 1: Found {candidate_job_emails} candidate job emails")
            
            # Stage 2: High Precision - Classify and save
            for message in candidate_emails:
                try:
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
                    
                    # Save to database (category will be converted to uppercase in _save_application)
                    self._save_application(user_id, message.get('id'), application_data, category, thread_id)
                    
                    # Update classified counts (category is already uppercase from classifier or will be normalized)
                    category_upper = category.upper()
                    if category_upper == "OFFER":
                        category_upper = "OFFER_ACCEPTED"
                    if category_upper in classified:
                        classified[category_upper] += 1
                    
                    # Yield progress update
                    yield {
                        "total_scanned": total_scanned,
                        "total_fetched": total_fetched,
                        "candidate_job_emails": candidate_job_emails,
                        "classified": classified.copy(),
                        "skipped": skipped,
                    }
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
        
        # Extract company and role using company extractor
        company = self.company_extractor.extract(subject, from_email, message.get('snippet', ''))
        role = self.company_extractor.extract_role(subject, message.get('snippet', ''))
        
        # Ensure company is never None - use fallback
        if not company:
            # Fallback: extract from email domain
            if '@' in from_email:
                domain = from_email.split('@')[1].lower()
                if domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com']:
                    company = domain.split('.')[0].capitalize()
                else:
                    company = 'Unknown Company'
            else:
                company = 'Unknown Company'
        
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
        Generate Gmail web URL for a message
        Format: https://mail.google.com/mail/u/0/#inbox/{message_id}
        """
        return f"https://mail.google.com/mail/u/0/#inbox/{message_id}"

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
            logger.warning(f"Invalid category: {category}, skipping")
            return
        
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
        
        # Check if application already exists
        existing = self.db.query(Application).filter(
            Application.gmail_message_id == gmail_message_id
        ).first()
        
        if existing:
            # Update existing
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
        else:
            # Create new
            application = Application(
                user_id=user_id,
                gmail_message_id=gmail_message_id,
                gmail_thread_id=thread_id,
                gmail_web_url=gmail_web_url,
                company_name=company_name,
                company_domain=company_domain,
                role=application_data.get("role"),
                category=category_upper,
                subject=subject,
                from_email=from_email,
                received_at=application_data.get("received_at"),
                snippet=application_data.get("snippet"),
            )
            self.db.add(application)
        
        self.db.commit()
