from typing import AsyncIterator, Dict, List
from sqlalchemy.orm import Session
from app.gmail_client import GmailClient
from app.classifier import Classifier
from app.hybrid_classifier import HybridClassifier
from app.company_extractor import CompanyExtractor
from app.database import Application, User
from datetime import datetime, timezone
import logging
import os

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
        # Set db session and gmail_client on classifier for enhanced features
        if hasattr(self.classifier, 'db'):
            self.classifier.db = db
        if hasattr(self.classifier, 'gmail_client'):
            self.classifier.gmail_client = gmail_client
        # If using hybrid classifier, ensure it has access to gmail_client
        if isinstance(self.classifier, HybridClassifier):
            self.classifier.gmail_client = gmail_client
            self.classifier.db = db
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
            # STEP 10: Batch classify (16-64) for ONNX speed
            # Optimized batch size: 16-64 emails per batch for ONNX inference speed
            # Smaller batches = lower memory usage, better cancellation responsiveness
            onnx_batch_size = int(os.getenv("ONNX_BATCH_SIZE", "32"))  # Default: 32 (between 16-64)
            onnx_batch_size = max(16, min(64, onnx_batch_size))  # Clamp between 16-64
            yield_batch_size = 50  # Yield progress every 50 emails
            batch_count = 0
            last_processed_message_id = None
            last_processed_internal_date = None
            
            # STEP 10: Batch classification for ONNX (16-64 emails at a time)
            # Collect emails for batch processing
            email_batch = []
            batch_results = {}
            
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
                    
                    # Check for attachments (for Layer 4: Structural Parsing)
                    # WHY: Attachments are strong signals (offer letters, calendar files)
                    application_data["has_attachment"] = self._has_attachments(message)
                    
                    # Extract headers for bulk detection (Layer 1)
                    application_data["headers"] = self._extract_headers(message)
                    
                    # Get thread ID from message
                    thread_id = message.get('threadId')
                    
                    # STEP 10: Build thread summary for ONNX classifier (batch processing)
                    thread_summary = ""
                    if thread_id and self.gmail_client:
                        try:
                            # Get thread for summary
                            thread = self.gmail_client.get_thread(thread_id)
                            if thread:
                                messages = thread.get('messages', [])
                                thread_summary = f"Thread has {len(messages)} messages"
                        except Exception as e:
                            logger.debug(f"Failed to get thread summary: {e}")
                    
                    # STEP 10: Add to batch for ONNX classification (16-64 emails at a time)
                    email_batch.append({
                        "message_id": message_id,
                        "message": message,
                        "application_data": application_data,
                        "thread_id": thread_id,
                        "thread_summary": thread_summary,
                        "internal_date": internal_date
                    })
                    
                    # STEP 10: Process batch when it reaches ONNX batch size (16-64)
                    if len(email_batch) >= onnx_batch_size:
                        batch_results.update(self._classify_batch_onnx(email_batch))
                        email_batch = []  # Clear batch
                    
                    # STEP 10: Get classification result from batch (or classify individually if not in batch)
                    onnx_result = batch_results.get(message_id)
                    if onnx_result is None:
                        # Fallback: classify individually (for non-ONNX or if batch failed)
                        try:
                            from app.services.classifier.hf_onnx_classifier import get_classifier
                            onnx_classifier = get_classifier()
                            
                            # Classify using ONNX (worker-only, not in request handlers)
                            onnx_result = onnx_classifier.classify_one(
                                subject=application_data.get("subject", ""),
                                snippet=application_data.get("snippet", ""),
                                from_domain=application_data.get("sender_domain", ""),
                                thread_summary=thread_summary
                            )
                        except RuntimeError:
                            # ONNX classifier not initialized - fall back to hybrid classifier
                            onnx_result = None
                        except Exception as e:
                            logger.debug(f"ONNX classification failed: {e}, falling back to hybrid classifier")
                            onnx_result = None
                    
                    # STEP 10: Track decision_path for full traceability
                    decision_path = []
                    
                    # Use ONNX result if available, otherwise use hybrid classifier
                    # STEP 8: Confidence threshold rules + guardrails
                    confidence_threshold = float(os.getenv("ONNX_CONFIDENCE_THRESHOLD", "0.75"))
                    needs_review = False
                    use_onnx_result = False
                    
                    if onnx_result:
                        decision_path.append("passed_ignore_filter")  # Layer 1 passed
                        onnx_confidence = onnx_result.get("confidence", 0.0)
                        onnx_status = onnx_result.get("status", "ACTIVE")
                        onnx_label = onnx_result.get("label", "")
                        from_domain = application_data.get("sender_domain", "").lower()
                        
                        # GUARDRAIL: If model says IGNORE but from_domain is ATS/company → re-check with rules
                        is_ats_or_company = False
                        ats_domains = ["greenhouse.io", "lever.co", "workday.com", "smartrecruiters.com", "jobvite.com"]
                        # Check if domain is ATS or looks like a company domain (not gmail/yahoo/hotmail)
                        if any(ats in from_domain for ats in ats_domains):
                            is_ats_or_company = True
                        elif from_domain and not any(noise in from_domain for noise in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]):
                            # Looks like a company domain (has company name in it)
                            if "." in from_domain and len(from_domain.split(".")[0]) > 2:
                                is_ats_or_company = True
                        
                        if onnx_status == "IGNORE" and is_ats_or_company:
                            # Guardrail triggered: IGNORE from ATS/company domain is suspicious
                            decision_path.append(f"hf_model:{onnx_label}:{onnx_confidence:.2f}")
                            decision_path.append("guardrail_ats_override")
                            logger.debug(f"Guardrail: ONNX said IGNORE but from_domain={from_domain} looks like ATS/company. Re-checking with rules.")
                            onnx_result = None  # Force fallback to rules
                        elif onnx_confidence >= confidence_threshold:
                            # Confidence threshold met → accept ONNX result
                            decision_path.append(f"hf_model:{onnx_label}:{onnx_confidence:.2f}")
                            use_onnx_result = True
                        else:
                            # Confidence too low → fallback to deterministic rules
                            decision_path.append(f"hf_model:{onnx_label}:{onnx_confidence:.2f}")
                            decision_path.append("low_confidence_fallback")
                            logger.debug(f"ONNX confidence {onnx_confidence} < threshold {confidence_threshold}. Falling back to rules.")
                            onnx_result = None  # Force fallback to rules
                    
                    if use_onnx_result and onnx_result:
                        # Map ONNX result to ClassificationResult format
                        from app.hybrid_classifier import ClassificationStatus, ClassificationResult, ClassificationSignals
                        
                        try:
                            status = ClassificationStatus(onnx_result["status"])
                        except ValueError:
                            status = ClassificationStatus.ACTIVE
                        
                        # Create ClassificationResult from ONNX output
                        classification_result = ClassificationResult(
                            status=status,
                            confidence=onnx_result["confidence"],
                            signals=ClassificationSignals(),  # ONNX doesn't provide signals
                            explanation=onnx_result["reason"],
                            version="1.0"
                        )
                        
                        # Handle IGNORE status (filtered emails)
                        if classification_result.status.value == "IGNORE":
                            skipped += 1
                            continue
                        
                        category = classification_result.status.value
                        # Add needs_review flag to explanation if set
                        reason = onnx_result["reason"]
                        if needs_review:
                            reason += " [NEEDS_REVIEW: Low confidence]"
                        
                        # STEP 10: Store status, label, confidence, model_version, decision_path
                        model_version = os.getenv("ONNX_MODEL_VERSION", "1.0")  # Model version for tracking
                        model_name = os.getenv("ONNX_MODEL_NAME", "job_email_classifier_v1")  # Model name
                        decision_path.append("saved")  # Final step
                        
                        classification_trace = {
                            "final_status": onnx_result["status"],
                            "confidence": onnx_result["confidence"],
                            "label": onnx_result["label"],  # Raw HF label (e.g., "confirmation", "interview")
                            "reason": reason,
                            "source": "ONNX",
                            "model_version": model_version,  # Model version for tracking
                            "model_name": model_name,  # Model name
                            "decision_path": decision_path,  # Decision path array
                            "needs_review": needs_review
                        }
                        
                        # Update explanation in classification_result
                        classification_result.explanation = reason
                        # Store model version in classification_result
                        classification_result.version = model_version
                    else:
                        # Fallback to hybrid classifier if ONNX not available
                        classification_result = None
                        classification_trace = {}
                    
                    if not use_onnx_result and isinstance(self.classifier, HybridClassifier):
                        # Fallback to hybrid classifier (deterministic rules)
                        # This happens when:
                        # 1. ONNX not available
                        # 2. ONNX confidence < threshold
                        # 3. Guardrail triggered (IGNORE from ATS/company)
                        if not decision_path:
                            decision_path.append("passed_ignore_filter")
                        decision_path.append("rules:hybrid_classifier")
                        
                        classification_result = self.classifier.classify(
                            email_data=application_data,
                            thread_id=thread_id,
                            company_name=application_data.get("company_name"),
                            role=application_data.get("role")
                        )
                        
                        # Handle IGNORE status (filtered emails)
                        if classification_result.status.value == "IGNORE":
                            decision_path.append("rules:ignore")
                            skipped += 1
                            continue
                        
                        category = classification_result.status.value
                        # Store enhanced traceability
                        classification_trace = classification_result.to_dict()
                        
                        # If still unsure after fallback → ACTIVE + needs_review=true
                        # Check if confidence is still low or status is ambiguous
                        if classification_result.confidence and classification_result.confidence < 0.6:
                            needs_review = True
                            category = "ACTIVE"  # Default to ACTIVE when unsure
                            decision_path.append("rules:active_low_conf")
                            decision_path.append("needs_review")
                            classification_trace["needs_review"] = True
                            classification_trace["fallback_reason"] = "Low confidence after rule-based classification"
                            # Update explanation to include needs_review flag
                            if classification_result.explanation:
                                classification_result.explanation += " [NEEDS_REVIEW: Low confidence after fallback]"
                            else:
                                classification_result.explanation = "Low confidence classification [NEEDS_REVIEW]"
                            logger.debug(f"Low confidence ({classification_result.confidence}) after fallback. Setting ACTIVE + needs_review=true")
                        else:
                            decision_path.append(f"rules:{category.lower()}:{classification_result.confidence:.2f}")
                        
                        # Add decision_path to classification_trace
                        classification_trace["decision_path"] = decision_path
                        decision_path.append("saved")  # Final step
                    elif not use_onnx_result:
                        # No ONNX and no HybridClassifier → default to ACTIVE + needs_review
                        from app.hybrid_classifier import ClassificationStatus, ClassificationResult, ClassificationSignals
                        needs_review = True
                        classification_result = ClassificationResult(
                            status=ClassificationStatus.ACTIVE,
                            confidence=0.5,
                            signals=ClassificationSignals(),
                            explanation="No classifier available - defaulting to ACTIVE",
                            version="1.0"
                        )
                        category = "ACTIVE"
                        classification_trace = {
                            "final_status": "ACTIVE",
                            "confidence": 0.5,
                            "reason": "No classifier available - defaulting to ACTIVE [NEEDS_REVIEW]",
                            "source": "DEFAULT",
                            "needs_review": True
                        }
                    else:
                        # Fallback to old classifier
                        thread_history = []
                        if hasattr(self.classifier, 'get_thread_history') and thread_id:
                            try:
                                thread_history = self.classifier.get_thread_history(str(user_id), thread_id)
                            except Exception as e:
                                logger.debug(f"Failed to get thread history: {e}")
                        
                        classification_result = self.classifier.classify(application_data, thread_history)
                        
                        if thread_history and hasattr(self.classifier, 'apply_thread_context'):
                            classification_result = self.classifier.apply_thread_context(
                                application_data,
                                thread_history,
                                classification_result
                            )
                        
                        if hasattr(classification_result, 'source') and classification_result.source.value == "FILTERED":
                            skipped += 1
                            continue
                        
                        category = classification_result.status.value if hasattr(classification_result, 'status') else str(classification_result)
                        classification_trace = classification_result.to_dict() if hasattr(classification_result, 'to_dict') else {}
                    
                    # IDEMPOTENCY: Save to database (upsert logic in _save_application prevents duplicates)
                    # CRITICAL: Track if save succeeded to ensure classified count matches saved count
                    try:
                        self._save_application(
                            user_id,
                            message_id,
                            application_data,
                            category,
                            thread_id,
                            classification_result,  # Works for both ONNX and HybridClassifier
                            classification_trace
                        )
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
                        
                        # Update classified counts (category is already uppercase from classifier)
                        category_upper = category.upper()
                        if category_upper == "OFFER":
                            category_upper = "OFFER"  # Keep as OFFER (not OFFER_ACCEPTED)
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
                    
                    # Process remaining batch if any
                    if len(email_batch) > 0:
                        batch_results.update(self._classify_batch_onnx(email_batch))
                        email_batch = []
                    
                    # Reset batch count after yielding (we still process in batches for efficiency)
                    if batch_count >= yield_batch_size:
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
        
        # Extract email body (for Layer 4: Structural Parsing)
        body = self._extract_email_body(message)
        
        # Extract sender domain
        sender_domain = ""
        if '@' in from_email:
            sender_domain = from_email.split('@')[1].lower()
        
        return {
            "company_name": company,
            "role": role,
            "subject": subject,
            "from_email": from_email,
            "sender_domain": sender_domain,
            "received_at": received_at,
            "snippet": message.get('snippet', ''),
            "body": body,  # Full body for structural parsing
        }
    
    def _extract_email_body(self, message: Dict) -> str:
        """
        Extract email body from Gmail message payload.
        
        WHY: Layer 4 (Structural Parsing) needs full body for:
        - Calendar detection
        - Date/time extraction
        - CTA phrase extraction
        - Action verb identification
        """
        try:
            payload = message.get('payload', {})
            
            def extract_from_part(part):
                """Recursively extract text/HTML from message parts"""
                mime_type = part.get('mimeType', '')
                
                # Extract text/html or text/plain
                if mime_type in ['text/html', 'text/plain']:
                    body_data = part.get('body', {}).get('data')
                    if body_data:
                        try:
                            import base64
                            decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                            return decoded
                        except:
                            return ""
                
                # Check multipart
                if 'multipart' in mime_type:
                    parts = part.get('parts', [])
                    for subpart in parts:
                        text = extract_from_part(subpart)
                        if text:
                            return text
                
                return ""
            
            body = extract_from_part(payload)
            
            # Strip email signatures (common patterns)
            # WHY: Signatures add noise and don't help classification
            body = self._strip_signature(body)
            
            return body
        except Exception as e:
            logger.debug(f"Error extracting email body: {e}")
            return ""
    
    def _has_attachments(self, message: Dict) -> bool:
        """
        Check if message has attachments.
        
        WHY: Attachments (especially offer letters, calendar files) are strong classification signals.
        """
        try:
            payload = message.get('payload', {})
            
            def check_part(part):
                # Check if part has attachment
                filename = part.get('filename', '')
                if filename:
                    return True
                
                # Check multipart
                if 'multipart' in part.get('mimeType', ''):
                    parts = part.get('parts', [])
                    for subpart in parts:
                        if check_part(subpart):
                            return True
                
                return False
            
            return check_part(payload)
        except:
            return False
    
    def _extract_headers(self, message: Dict) -> Dict:
        """
        Extract email headers for bulk detection.
        
        WHY: Bulk headers help identify marketing/newsletter emails (Layer 1).
        """
        try:
            payload = message.get('payload', {})
            headers = payload.get('headers', [])
            
            header_dict = {}
            for header in headers:
                name = header.get('name', '')
                value = header.get('value', '')
                header_dict[name] = value
            
            return header_dict
        except:
            return {}
    
    def _classify_batch_onnx(self, email_batch: List[Dict]) -> Dict[str, Dict]:
        """
        STEP 10: Batch classify emails using ONNX (16-64 emails at a time for speed).
        
        Args:
            email_batch: List of email data dictionaries with keys:
                - message_id: Gmail message ID
                - application_data: Extracted application data
                - thread_summary: Thread summary string
        
        Returns:
            Dictionary mapping message_id -> ONNX classification result
        """
        results = {}
        
        if not email_batch:
            return results
        
        try:
            from app.services.classifier.hf_onnx_classifier import get_classifier
            onnx_classifier = get_classifier()
            
            # Prepare batch items for classify_batch
            batch_items = []
            message_ids = []
            
            for email_data in email_batch:
                batch_items.append({
                    "subject": email_data["application_data"].get("subject", ""),
                    "snippet": email_data["application_data"].get("snippet", ""),
                    "from_domain": email_data["application_data"].get("sender_domain", ""),
                    "thread_summary": email_data.get("thread_summary", "")
                })
                message_ids.append(email_data["message_id"])
            
            # STEP 10: Batch classify (16-64 emails at once) - much faster than individual calls
            batch_results = onnx_classifier.classify_batch(batch_items)
            
            # Map results back to message IDs
            for i, result in enumerate(batch_results):
                if i < len(message_ids):
                    results[message_ids[i]] = result
            
            logger.debug(f"Batch classified {len(batch_results)} emails using ONNX (batch size: {len(email_batch)})")
            
        except RuntimeError:
            # ONNX classifier not initialized
            logger.debug("ONNX classifier not available for batch classification")
        except Exception as e:
            logger.debug(f"Batch ONNX classification failed: {e}")
        
        return results
    
    def _strip_signature(self, text: str) -> str:
        """
        Strip email signatures from body text.
        
        WHY: Signatures contain contact info, disclaimers, etc. that don't help classification.
        """
        if not text:
            return text
        
        # Common signature patterns
        signature_patterns = [
            r'--\s*\n',  # Standard signature delimiter
            r'Sent from.*',  # Mobile signatures
            r'Best regards.*',  # Common closings
            r'Regards,.*',
            r'Thanks,.*',
            r'This email.*confidential.*',  # Disclaimers
            r'CONFIDENTIALITY.*',
        ]
        
        # Find first signature marker and remove everything after
        for pattern in signature_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                text = text[:match.start()]
                break
        
        return text
    
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
        thread_id: str = None,
        classification_result = None,  # ClassificationResult object with traceability
        classification_trace: Dict = None  # Enhanced traceability dict
    ):
        """
        Save application to database (upsert)
        Ensures company_name is never null
        Category must be uppercase: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, GHOSTED
        Generates gmail_web_url and extracts company_domain
        """
        # Ensure category is uppercase
        category_upper = category.upper() if category != "skip" else None
        # Keep OFFER as OFFER (not OFFER_ACCEPTED) for new classification system
        # Map ACTIVE to APPLIED for backward compatibility if needed
        if category_upper == "ACTIVE":
            category_upper = "ACTIVE"  # Use ACTIVE (new system)
        elif category_upper == "OFFER":
            category_upper = "OFFER"  # Use OFFER (new system)
        
        valid_categories = ["ACTIVE", "APPLIED", "REJECTED", "INTERVIEW", "OFFER", "OFFER_ACCEPTED", "GHOSTED", "WITHDRAWN"]
        if not category_upper or category_upper not in valid_categories:
            logger.warning(f"Invalid category: {category}, cannot save")
            # CRITICAL: Raise exception so caller knows save failed (for verification)
            # This ensures classified count matches saved count
            raise ValueError(f"Invalid category '{category}' - cannot save application")
        
        # Extract classification traceability fields
        classification_source = None
        rule_name = None
        llm_reason = None
        classification_confidence = None
        signals_used = None
        rules_triggered = None
        classification_version = None
        
        if classification_result and hasattr(classification_result, 'signals'):
            # Hybrid classifier result
            signals = classification_result.signals
            classification_source = "HYBRID"
            rule_name = ", ".join(signals.matched_rules[:3]) if signals.matched_rules else None
            llm_reason = signals.llm_reason
            classification_confidence = str(classification_result.confidence)
            signals_used = signals.signals_used
            rules_triggered = signals.rules_triggered
            classification_version = classification_result.version
        elif classification_result:
            # Old classifier result
            if hasattr(classification_result, 'source'):
                classification_source = classification_result.source.value
            if hasattr(classification_result, 'rule_name'):
                rule_name = classification_result.rule_name
            if hasattr(classification_result, 'llm_reason'):
                llm_reason = classification_result.llm_reason
            if hasattr(classification_result, 'confidence') and classification_result.confidence is not None:
                classification_confidence = str(classification_result.confidence)
        
        # Use enhanced traceability if available
        needs_review = False
        model_version = None
        model_name = None
        onnx_label = None  # Raw HF label from ONNX
        decision_path = None
        if classification_trace:
            signals_used = classification_trace.get("signals_used") or []
            rules_triggered = classification_trace.get("rules_triggered")
            classification_version = classification_trace.get("version") or classification_trace.get("model_version")
            model_version = classification_trace.get("model_version")  # STEP 10: Store model_version
            model_name = classification_trace.get("model_name")  # STEP 10: Store model_name
            onnx_label = classification_trace.get("label")  # STEP 10: Store raw HF label
            decision_path = classification_trace.get("decision_path")  # STEP 10: Store decision_path
            needs_review = classification_trace.get("needs_review", False)
            
            # Add needs_review to signals_used for querying
            if needs_review and isinstance(signals_used, list) and "needs_review" not in signals_used:
                signals_used = signals_used + ["needs_review"]
        
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
            # Check if category changed (for audit log and activity tracking)
            old_category = existing.category
            category_changed = old_category != category_upper
            
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
            # Update classification traceability fields
            if hasattr(existing, 'classification_source'):
                existing.classification_source = classification_source
            if hasattr(existing, 'rule_name'):
                existing.rule_name = rule_name
            if hasattr(existing, 'llm_reason'):
                existing.llm_reason = llm_reason
            if hasattr(existing, 'classification_confidence'):
                existing.classification_confidence = classification_confidence
            if hasattr(existing, 'classified_at'):
                existing.classified_at = datetime.now(timezone.utc)
            # Enhanced traceability (9-layer pipeline)
            if hasattr(existing, 'signals_used'):
                existing.signals_used = signals_used
            if hasattr(existing, 'rules_triggered'):
                existing.rules_triggered = rules_triggered
            # STEP 10: Store model_version, model_name, raw_label, decision_path
            if hasattr(existing, 'classification_version'):
                existing.classification_version = model_version or classification_version
            if hasattr(existing, 'model_name'):
                existing.model_name = model_name
            if hasattr(existing, 'raw_label'):
                existing.raw_label = onnx_label
            if hasattr(existing, 'decision_path'):
                existing.decision_path = decision_path
            # Store ONNX label in signals_used for querying
            if onnx_label and isinstance(signals_used, list):
                current_signals = existing.signals_used or []
                if not any("onnx_label:" in str(s) for s in current_signals):
                    existing.signals_used = current_signals + [f"onnx_label:{onnx_label}"]
            # Update last_activity_at if category changed (status change = activity)
            if hasattr(existing, 'last_activity_at'):
                if category_changed:
                    existing.last_activity_at = datetime.now(timezone.utc)
                elif not existing.last_activity_at:
                    existing.last_activity_at = last_activity_at_value
            
            # Create audit log entry if category changed
            if category_changed and classification_result:
                from app.database import ClassificationAuditLog
                audit_log = ClassificationAuditLog(
                    application_id=existing.id,
                    old_status=old_category,
                    new_status=category_upper,
                    reason=classification_result.reason,
                    classification_source=classification_source,
                    rule_name=rule_name,
                    confidence=classification_confidence
                )
                self.db.add(audit_log)
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
            # Add classification traceability fields
            if hasattr(Application, 'classification_source'):
                app_data['classification_source'] = classification_source
            if hasattr(Application, 'rule_name'):
                app_data['rule_name'] = rule_name
            if hasattr(Application, 'llm_reason'):
                app_data['llm_reason'] = llm_reason
            if hasattr(Application, 'classification_confidence'):
                app_data['classification_confidence'] = classification_confidence
            if hasattr(Application, 'classified_at'):
                app_data['classified_at'] = datetime.now(timezone.utc)
            # Enhanced traceability (9-layer pipeline)
            if hasattr(Application, 'signals_used'):
                app_data['signals_used'] = signals_used
            if hasattr(Application, 'rules_triggered'):
                app_data['rules_triggered'] = rules_triggered
            # STEP 10: Store model_version, model_name, raw_label, decision_path
            if hasattr(Application, 'classification_version'):
                app_data['classification_version'] = model_version or classification_version
            if hasattr(Application, 'model_name'):
                app_data['model_name'] = model_name
            if hasattr(Application, 'raw_label'):
                app_data['raw_label'] = onnx_label
            if hasattr(Application, 'decision_path'):
                app_data['decision_path'] = decision_path
            # Store ONNX label in signals_used for querying
            if onnx_label and isinstance(signals_used, list):
                if not any("onnx_label:" in str(s) for s in signals_used):
                    signals_used = signals_used + [f"onnx_label:{onnx_label}"]
                if hasattr(Application, 'signals_used'):
                    app_data['signals_used'] = signals_used
            if hasattr(Application, 'rules_triggered'):
                app_data['rules_triggered'] = rules_triggered
            if hasattr(Application, 'needs_review'):
                app_data['needs_review'] = needs_review
            if hasattr(Application, 'classification_version'):
                app_data['classification_version'] = classification_version
            
            application = Application(**app_data)
            self.db.add(application)
        
        self.db.commit()
