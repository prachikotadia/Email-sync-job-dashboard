from typing import AsyncIterator, Dict, List
from sqlalchemy.orm import Session
from app.gmail_client import GmailClient
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor
from app.database import Application, User
from datetime import datetime
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
            "applied": 0,
            "rejected": 0,
            "interview": 0,
            "offer": 0,
            "ghosted": 0,
        }
        skipped = 0
        
        # Query for job-related emails (Stage 1 - High Recall)
        query = "subject:(application OR applied OR interview OR offer OR rejection OR thank you OR hiring OR position)"
        
        try:
            # Get total count first (estimate)
            total_count = self.gmail_client.get_message_count(query)
            total_scanned = total_count
            
            logger.info(f"Starting sync for user {user_id}: Estimated {total_count} emails to scan")
            
            # Fetch ALL messages (incremental if historyId exists)
            messages, latest_history_id = self.gmail_client.get_all_messages(query, existing_history_id)
            self.latest_history_id = latest_history_id
            total_fetched = len(messages)
            
            logger.info(f"Fetched {total_fetched} messages from Gmail API")
            
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
                    
                    # Save to database
                    self._save_application(user_id, message.get('id'), application_data, category)
                    
                    # Update classified counts
                    if category in classified:
                        classified[category] += 1
                    
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
                f"Applied: {classified['applied']}, Rejected: {classified['rejected']}, "
                f"Interview: {classified['interview']}, Offer: {classified['offer']}, "
                f"Ghosted: {classified['ghosted']}. Skipped: {skipped}."
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
        
        # Parse date
        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()
        except:
            received_at = datetime.utcnow()
        
        # Extract company and role using company extractor
        company = self.company_extractor.extract(subject, from_email, message.get('snippet', ''))
        role = self.company_extractor.extract_role(subject, message.get('snippet', ''))
        
        if not company:
            return None
        
        return {
            "company_name": company,
            "role": role,
            "subject": subject,
            "from_email": from_email,
            "received_at": received_at,
            "snippet": message.get('snippet', ''),
        }
    
    def _save_application(
        self,
        user_id: int,
        gmail_message_id: str,
        application_data: Dict,
        category: str
    ):
        """
        Save application to database (upsert)
        """
        # Check if application already exists
        existing = self.db.query(Application).filter(
            Application.gmail_message_id == gmail_message_id
        ).first()
        
        if existing:
            # Update existing
            existing.company_name = application_data["company_name"]
            existing.role = application_data.get("role")
            existing.category = category
            existing.subject = application_data.get("subject")
            existing.from_email = application_data.get("from_email")
            existing.received_at = application_data.get("received_at")
            existing.snippet = application_data.get("snippet")
            existing.last_updated = datetime.utcnow()
        else:
            # Create new
            application = Application(
                user_id=user_id,
                gmail_message_id=gmail_message_id,
                company_name=application_data["company_name"],
                role=application_data.get("role"),
                category=category,
                subject=application_data.get("subject"),
                from_email=application_data.get("from_email"),
                received_at=application_data.get("received_at"),
                snippet=application_data.get("snippet"),
            )
            self.db.add(application)
        
        self.db.commit()
