from typing import AsyncIterator, Dict, List, Optional
from sqlalchemy.orm import Session
from app.gmail_client import GmailClient
from app.classifier import Classifier
from app.company_extractor import CompanyExtractor, ParsedEmail, CompanyExtractionResult
from app.database import Application, User
from datetime import datetime, timezone
import logging
import json
import base64
import uuid

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
    
    async def sync_all_emails(
        self,
        user_id: uuid.UUID,
        existing_history_id: str = None,
        job_manager: Optional[object] = None,
        job_id: Optional[uuid.UUID] = None
    ) -> AsyncIterator[Dict]:
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
            
            # Log to job if available
            if job_manager and job_id:
                job_manager.log(job_id, "INFO", f"Starting sync: Estimated {total_count} emails to scan")
                job_manager.update_progress(job_id, total_estimated=total_count, phase="FETCHING")
            
            # Fetch ALL messages (incremental if historyId exists)
            # This MUST paginate until nextPageToken is null - NO early exit
            messages, latest_history_id = self.gmail_client.get_all_messages(query, existing_history_id)
            self.latest_history_id = latest_history_id
            total_fetched = len(messages)
            
            # Logging MUST match requirements: "Total Gmail emails: X, Fetched: X"
            logger.info(f"Total Gmail emails: {total_scanned}")
            logger.info(f"Fetched messages: {total_fetched}")
            
            # Update job progress with detailed logging
            if job_manager and job_id:
                job_manager.log(job_id, "INFO", f"📧 Total Gmail emails found: {total_scanned}")
                job_manager.log(job_id, "INFO", f"📥 Fetched {total_fetched} emails from Gmail API")
                job_manager.update_progress(job_id, emails_fetched=total_fetched, phase="CLASSIFYING")
                job_manager.log(job_id, "INFO", f"🔄 Starting Stage 1: High-recall filtering of {total_fetched} emails...")
            
            # Verify: If X ≠ X → BUG (but allow for API estimate vs actual)
            if total_fetched < total_scanned * 0.9:  # Allow 10% variance for API estimates
                logger.warning(f"Fetched count ({total_fetched}) significantly less than estimated ({total_scanned}). May indicate pagination issue.")
                if job_manager and job_id:
                    job_manager.log(job_id, "WARN", f"Fetched count ({total_fetched}) less than estimated ({total_scanned})")
            
            # Stage 1: High Recall - Filter candidate job emails
            candidate_emails = []
            stage1_processed = 0
            stage1_batch_size = 50  # Log every 50 emails during Stage 1
            for message in messages:
                try:
                    if self._is_candidate_job_email(message):
                        candidate_emails.append(message)
                        candidate_job_emails += 1
                    else:
                        skipped += 1
                    stage1_processed += 1
                    
                    # Log progress every 50 emails during Stage 1 for real-time updates
                    if job_manager and job_id and stage1_processed % stage1_batch_size == 0:
                        job_manager.log(job_id, "INFO", f"🔍 Stage 1: Processed {stage1_processed}/{total_fetched} emails, found {candidate_job_emails} job candidates so far...")
                except Exception as e:
                    logger.warning(f"Error checking message {message.get('id')}: {e}")
                    skipped += 1
                    stage1_processed += 1
                    continue
            
            logger.info(f"Stage 1: Found {candidate_job_emails} candidate job emails")
            
            if job_manager and job_id:
                job_manager.log(job_id, "INFO", f"Stage 1 complete: Identified {candidate_job_emails} job-related emails out of {total_fetched} total")
                job_manager.log(job_id, "INFO", f"Starting Stage 2: High-precision classification of {candidate_job_emails} candidate emails...")
            
            # Stage 2: High Precision - Classify and save
            processed_count = 0
            log_batch_size = 10  # Log every 10 items
            db_commit_batch_size = 50  # Commit to DB every 50 items (reduces DB load for large batches)
            pending_applications = []  # Batch database commits
            
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
                    
                    # Prepare application for batch save (don't commit yet)
                    pending_applications.append((user_id, message.get('id'), application_data, category, thread_id))
                    
                    # Update classified counts (category is already uppercase from classifier or will be normalized)
                    category_upper = category.upper()
                    if category_upper == "OFFER":
                        category_upper = "OFFER_ACCEPTED"
                    if category_upper in classified:
                        classified[category_upper] += 1
                    
                    processed_count += 1
                    
                    # Batch commit to database every N applications (reduces DB load for 2000+ emails)
                    if len(pending_applications) >= db_commit_batch_size:
                        try:
                            for uid, msg_id, app_data, cat, tid in pending_applications:
                                self._save_application(uid, msg_id, app_data, cat, tid)
                            self.db.commit()
                            pending_applications = []
                        except Exception as e:
                            logger.error(f"Error batch committing applications: {e}")
                            self.db.rollback()
                            # Try individual saves as fallback
                            for uid, msg_id, app_data, cat, tid in pending_applications:
                                try:
                                    self._save_application(uid, msg_id, app_data, cat, tid)
                                    self.db.commit()
                                except Exception as save_error:
                                    logger.warning(f"Error saving application {msg_id}: {save_error}")
                                    self.db.rollback()
                            pending_applications = []
                    
                    # Update job progress more frequently (every 10 items or at end) for real-time updates
                    if job_manager and job_id and (processed_count % log_batch_size == 0 or processed_count == len(candidate_emails)):
                        # Convert classified dict keys to lowercase for API response
                        category_counts_lower = {k.lower(): v for k, v in classified.items()}
                        job_manager.update_progress(
                            job_id,
                            emails_classified=processed_count,
                            applications_stored=sum(classified.values()),
                            skipped=skipped,
                            category_counts=category_counts_lower,
                            phase="STORING"
                        )
                        # Log progress every batch for real-time feedback
                        if processed_count % log_batch_size == 0:
                            applied_count = classified.get('APPLIED', 0)
                            rejected_count = classified.get('REJECTED', 0)
                            interview_count = classified.get('INTERVIEW', 0)
                            offer_count = classified.get('OFFER_ACCEPTED', 0)
                            job_manager.log(job_id, "INFO", f"📊 Classified {processed_count}/{len(candidate_emails)} emails | Stored: {sum(classified.values())} apps (Applied: {applied_count}, Rejected: {rejected_count}, Interview: {interview_count}, Offer: {offer_count})")
                    
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
            
            # Commit any remaining pending applications
            if pending_applications:
                try:
                    for uid, msg_id, app_data, cat, tid in pending_applications:
                        self._save_application(uid, msg_id, app_data, cat, tid)
                    self.db.commit()
                except Exception as e:
                    logger.error(f"Error committing final batch of applications: {e}")
                    self.db.rollback()
                    # Try individual saves as fallback
                    for uid, msg_id, app_data, cat, tid in pending_applications:
                        try:
                            self._save_application(uid, msg_id, app_data, cat, tid)
                            self.db.commit()
                        except Exception as save_error:
                            logger.warning(f"Error saving application {msg_id}: {save_error}")
                            self.db.rollback()
            
            logger.info(
                f"Fetched: {total_fetched} emails. Job-related candidates: {candidate_job_emails}. "
                f"APPLIED: {classified['APPLIED']}, REJECTED: {classified['REJECTED']}, "
                f"INTERVIEW: {classified['INTERVIEW']}, OFFER_ACCEPTED: {classified['OFFER_ACCEPTED']}, "
                f"GHOSTED: {classified['GHOSTED']}. Skipped: {skipped}."
            )
            
            # Final job update
            if job_manager and job_id:
                category_counts_lower = {k.lower(): v for k, v in classified.items()}
                job_manager.update_progress(
                    job_id,
                    emails_classified=candidate_job_emails,
                    applications_stored=sum(classified.values()),
                    skipped=skipped,
                    category_counts=category_counts_lower,
                    phase="FINALIZING"
                )
                # Detailed completion logs
                job_manager.log(job_id, "INFO", f"✅ Sync complete! Processed {total_fetched} emails, found {candidate_job_emails} job-related emails")
                job_manager.log(job_id, "INFO", f"📊 Final counts: {sum(classified.values())} applications stored")
                job_manager.log(job_id, "INFO", f"   - Applied: {classified.get('APPLIED', 0)}, Rejected: {classified.get('REJECTED', 0)}, Interview: {classified.get('INTERVIEW', 0)}")
                job_manager.log(job_id, "INFO", f"   - Offer/Accepted: {classified.get('OFFER_ACCEPTED', 0)}, Ghosted: {classified.get('GHOSTED', 0)}, Skipped: {skipped}")
            
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
        
        # Extract body text if available for better company name extraction
        body_text = ""
        try:
            payload = message.get('payload', {})
            # Check if body is directly in payload
            if 'body' in payload and payload['body'].get('data'):
                import base64
                body_text = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
            # Check parts for body text
            elif 'parts' in payload:
                for part in payload.get('parts', []):
                    if part.get('mimeType') == 'text/plain' and 'body' in part:
                        body_data = part.get('body', {}).get('data', '')
                        if body_data:
                            import base64
                            body_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                            break
        except Exception as e:
            logger.debug(f"Could not extract body text: {e}")
        
        # Build ParsedEmail object for new extractor
        parsed_email = ParsedEmail(
            from_email=from_email,
            from_name=from_email.split('<')[0].strip().strip('"') if '<' in from_email else '',
            reply_to_email=None,  # Will be extracted from headers below
            subject=subject,
            snippet=message.get('snippet', ''),
            headers={h.get('name', '').lower(): h.get('value', '') for h in headers},
            list_unsubscribe=None,  # Will be extracted from headers below
            body_text=body_text,
            body_html=None,
            received_at=date_str,
            message_id=message.get('id', ''),
            thread_id=message.get('threadId', '')
        )
        
        # Extract reply-to and list-unsubscribe from headers
        for header in headers:
            name = header.get('name', '').lower()
            value = header.get('value', '')
            if name == 'reply-to':
                parsed_email.reply_to_email = value
            elif name == 'list-unsubscribe':
                parsed_email.list_unsubscribe = value
        
        # Extract company using new extractor
        extraction_result: CompanyExtractionResult = self.company_extractor.extract_company_name(
            parsed_email, 
            user_email=""  # Can be passed if available
        )
        
        company = extraction_result.company_name
        role = self.company_extractor.extract_role(subject, message.get('snippet', ''))
        
        # Ensure company is never None
        if not company or company.strip() == '':
            company = 'Unknown'
        
        return {
            "company_name": company,
            "company_confidence": extraction_result.confidence,
            "company_source": extraction_result.source,
            "company_raw_candidates": json.dumps(extraction_result.candidates),
            "ats_provider": extraction_result.ats_provider,
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
        
        # Extract company extraction fields
        company_name = application_data.get("company_name", "Unknown")
        company_confidence = application_data.get("company_confidence", 0)
        company_source = application_data.get("company_source", "UNKNOWN")
        company_raw_candidates = application_data.get("company_raw_candidates", "[]")
        ats_provider = application_data.get("ats_provider")
        
        # Ensure company_name is never null
        if not company_name or company_name.strip() == '':
            company_name = 'Unknown'
            company_confidence = 0
            company_source = 'UNKNOWN'
        
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
            existing.company_confidence = company_confidence
            existing.company_source = company_source
            existing.company_raw_candidates = company_raw_candidates
            existing.ats_provider = ats_provider
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
                company_confidence=company_confidence,
                company_source=company_source,
                company_raw_candidates=company_raw_candidates,
                ats_provider=ats_provider,
                role=application_data.get("role"),
                category=category_upper,
                subject=subject,
                from_email=from_email,
                received_at=application_data.get("received_at"),
                snippet=application_data.get("snippet"),
            )
            self.db.add(application)
        
        self.db.commit()
