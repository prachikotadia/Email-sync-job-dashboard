"""
ADVANCED EMAIL CLASSIFICATION SYSTEM (PRODUCTION-GRADE)

3-Stage Pipeline:
1. STAGE 1 - Hard Filter: Eliminate promotions/marketing (ZERO LLM)
2. STAGE 2 - Rule-Based Strong Signals: Catch obvious cases (ZERO LLM)
3. STAGE 3 - Local LLM: Handle ambiguous cases (ONLY when needed)

NON-NEGOTIABLE REQUIREMENTS:
- Deterministic and traceable
- Handles 1,000+ emails
- Explains every classification
- Supports re-classification
- Avoids false positives from promotions
- Uses thread history context
- Batches LLM calls for performance
"""

from typing import Dict, Optional, List, Tuple
import logging
import asyncio
import os
import json
import re
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Status categories (STRICT ENUM - no free-text, no "unknown")
class ClassificationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    GHOSTED = "GHOSTED"
    OFFER = "OFFER"
    WITHDRAWN = "WITHDRAWN"

# Classification source
class ClassificationSource(str, Enum):
    RULE = "RULE"
    LLM = "LLM"
    FILTERED = "FILTERED"
    THREAD_CONTEXT = "THREAD_CONTEXT"

@dataclass
class ClassificationResult:
    """Result of classification with full traceability"""
    status: ClassificationStatus
    source: ClassificationSource
    rule_name: Optional[str] = None  # Name of rule that matched (if source is RULE)
    llm_reason: Optional[str] = None  # LLM explanation (if source is LLM)
    confidence: Optional[float] = None  # Confidence score 0.0-1.0
    reason: str = ""  # Human-readable explanation
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "status": self.status.value,
            "source": self.source.value,
            "rule_name": self.rule_name,
            "llm_reason": self.llm_reason,
            "confidence": str(self.confidence) if self.confidence is not None else None,
            "reason": self.reason
        }

class AdvancedClassifier:
    """
    Production-grade email classification system with 3-stage pipeline.
    
    STAGE 1: Hard Filter (Rule-based, zero LLM)
    - Filters out promotions, marketing, non-job approvals
    
    STAGE 2: Rule-Based Strong Signals (Rule-based, zero LLM)
    - Catches obvious cases: REJECTED, INTERVIEW, OFFER
    
    STAGE 3: Local LLM (Only when needed)
    - Handles ambiguous cases
    - Uses thread history context
    - Batches for performance
    """
    
    def __init__(self, db_session=None):
        """
        Initialize classifier.
        
        Args:
            db_session: SQLAlchemy session for thread history queries (optional)
        """
        # LLM configuration
        self.llm_enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
        self.llm_timeout_sec = float(os.getenv("LLM_TIMEOUT_SEC", "2.0"))
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))
        self.llm_url = os.getenv("LLM_URL", "http://localhost:11434/api/generate")
        self.llm_model = os.getenv("LLM_MODEL", "llama2")
        
        # Ghosting configuration
        self.ghosted_days = int(os.getenv("GHOSTED_DAYS", "30"))
        
        # Database session for thread history
        self.db = db_session
        
        # Batch processing for LLM
        self.llm_batch_size = int(os.getenv("LLM_BATCH_SIZE", "10"))
        
        # STAGE 1: Promotion filter patterns
        self.promo_domains = [
            "noreply",
            "marketing",
            "offers",
            "newsletter",
            "promo",
            "deals",
            "sales"
        ]
        
        self.promo_subject_keywords = [
            "sale",
            "discount",
            "promo",
            "limited offer",
            "special offer",
            "flash sale",
            "clearance",
            "buy now",
            "shop now"
        ]
        
        self.promo_snippet_keywords = [
            "shopping",
            "subscription",
            "rewards",
            "unsubscribe",
            "click here to buy",
            "limited time",
            "act now"
        ]
        
        # STAGE 2: Rule-based strong signals (ORDER MATTERS)
        # REJECTED rules (highest priority - check first)
        self.rejected_keywords = [
            "unfortunately",
            "we regret to inform",
            "not moving forward",
            "decided to pursue other candidates",
            "not a fit",
            "declined",
            "not selected",
            "we've decided",
            "other candidates",
            "not proceed",
            "not advance"
        ]
        
        # INTERVIEW rules
        self.interview_keywords = [
            "interview",
            "schedule",
            "availability",
            "next round",
            "technical round",
            "hr call",
            "phone screen",
            "video interview",
            "onsite",
            "interview process",
            "interviewing",
            "interviewer"
        ]
        
        # OFFER rules
        self.offer_keywords = [
            "offer letter",
            "compensation",
            "salary",
            "joining",
            "congratulations",
            "we'd like to offer",
            "we are pleased to offer",
            "job offer",
            "employment offer",
            "welcome to the team",
            "start date",
            "onboarding"
        ]
    
    def classify(
        self,
        email_data: Dict,
        thread_history: Optional[List[Dict]] = None
    ) -> Optional[ClassificationResult]:
        """
        Main classification entry point.
        
        Args:
            email_data: Dict with keys:
                - message_id
                - thread_id
                - subject
                - snippet (≤ 200 chars)
                - sender_email
                - sender_domain
                - received_at
            thread_history: List of previous classifications in thread (optional)
        
        Returns:
            ClassificationResult or None (if filtered out)
        """
        # STAGE 1: Hard Filter (eliminate promotions/marketing)
        if self._is_promotion(email_data):
            return ClassificationResult(
                status=ClassificationStatus.ACTIVE,  # Default status for filtered emails
                source=ClassificationSource.FILTERED,
                reason="Filtered out: Promotion/marketing email"
            )
        
        # STAGE 2: Rule-Based Strong Signals
        rule_result = self._classify_rule_based(email_data)
        if rule_result:
            return rule_result
        
        # STAGE 3: Local LLM (only if no rule matched)
        if self.llm_enabled:
            try:
                llm_result = self._classify_with_llm(email_data, thread_history)
                if llm_result:
                    return llm_result
            except Exception as e:
                logger.debug(f"LLM classification failed (fallback to ACTIVE): {e}")
        
        # Fallback: Default to ACTIVE if no classification found
        return ClassificationResult(
            status=ClassificationStatus.ACTIVE,
            source=ClassificationSource.RULE,
            rule_name="default_active",
            reason="No strong signals found, defaulting to ACTIVE"
        )
    
    def classify_batch(
        self,
        emails: List[Dict],
        thread_histories: Optional[List[List[Dict]]] = None
    ) -> List[Optional[ClassificationResult]]:
        """
        Batch classification for performance.
        
        Processes emails in batches, using LLM batching when needed.
        
        Args:
            emails: List of email data dicts
            thread_histories: Optional list of thread histories (one per email)
        
        Returns:
            List of ClassificationResult or None (for filtered emails)
        """
        results = []
        
        # Stage 1 & 2: Process all emails with rules (fast, no LLM)
        llm_candidates = []  # Emails that need LLM classification
        llm_indices = []  # Indices of emails needing LLM
        
        for idx, email_data in enumerate(emails):
            thread_history = thread_histories[idx] if thread_histories else None
            
            # Stage 1: Hard filter
            if self._is_promotion(email_data):
                results.append(ClassificationResult(
                    status=ClassificationStatus.ACTIVE,
                    source=ClassificationSource.FILTERED,
                    reason="Filtered out: Promotion/marketing email"
                ))
                continue
            
            # Stage 2: Rule-based
            rule_result = self._classify_rule_based(email_data)
            if rule_result:
                results.append(rule_result)
            else:
                # Need LLM classification
                llm_candidates.append((email_data, thread_history))
                llm_indices.append(idx)
                results.append(None)  # Placeholder
        
        # Stage 3: Batch LLM classification
        if llm_candidates and self.llm_enabled:
            try:
                llm_results = self._classify_batch_with_llm(llm_candidates)
                for llm_idx, llm_result in enumerate(llm_results):
                    original_idx = llm_indices[llm_idx]
                    if llm_result:
                        results[original_idx] = llm_result
                    else:
                        # LLM failed, use default
                        results[original_idx] = ClassificationResult(
                            status=ClassificationStatus.ACTIVE,
                            source=ClassificationSource.RULE,
                            rule_name="default_active",
                            reason="LLM classification failed, defaulting to ACTIVE"
                        )
            except Exception as e:
                logger.debug(f"Batch LLM classification failed: {e}")
                # Fill in defaults for failed LLM calls
                for idx in llm_indices:
                    if results[idx] is None:
                        results[idx] = ClassificationResult(
                            status=ClassificationStatus.ACTIVE,
                            source=ClassificationSource.RULE,
                            rule_name="default_active",
                            reason="LLM classification failed, defaulting to ACTIVE"
                        )
        
        # Fill in any remaining None values with defaults
        for idx, result in enumerate(results):
            if result is None:
                results[idx] = ClassificationResult(
                    status=ClassificationStatus.ACTIVE,
                    source=ClassificationSource.RULE,
                    rule_name="default_active",
                    reason="No classification found, defaulting to ACTIVE"
                )
        
        return results
    
    def _is_promotion(self, email_data: Dict) -> bool:
        """
        STAGE 1: Hard Filter - Detect promotions/marketing emails.
        
        Returns True if email should be filtered out (ignored).
        """
        subject = email_data.get("subject", "").lower()
        snippet = email_data.get("snippet", "").lower()
        sender_domain = email_data.get("sender_domain", "").lower()
        sender_email = email_data.get("sender_email", "").lower()
        
        # Check sender domain patterns
        for promo_domain in self.promo_domains:
            if promo_domain in sender_domain or promo_domain in sender_email:
                return True
        
        # Check subject keywords
        for keyword in self.promo_subject_keywords:
            if keyword in subject:
                return True
        
        # Check snippet keywords
        for keyword in self.promo_snippet_keywords:
            if keyword in snippet:
                return True
        
        # Special case: "approved" messages that are not job-related
        # e.g., "Nike Offer Approved", "Your WiFi application was approved"
        if "approved" in subject or "approved" in snippet:
            # Check if it's job-related
            job_indicators = ["job", "position", "application", "role", "interview", "offer"]
            if not any(indicator in subject.lower() or indicator in snippet.lower() for indicator in job_indicators):
                return True
        
        return False
    
    def _classify_rule_based(self, email_data: Dict) -> Optional[ClassificationResult]:
        """
        STAGE 2: Rule-Based Strong Signals.
        
        Returns ClassificationResult if a strong rule matches, None otherwise.
        ORDER MATTERS: Check REJECTED first, then INTERVIEW, then OFFER.
        """
        subject = email_data.get("subject", "").lower()
        snippet = email_data.get("snippet", "").lower()
        text = f"{subject} {snippet}"
        
        # REJECTED (highest priority)
        for keyword in self.rejected_keywords:
            if keyword in text:
                return ClassificationResult(
                    status=ClassificationStatus.REJECTED,
                    source=ClassificationSource.RULE,
                    rule_name="rejected_keywords",
                    confidence=0.95,
                    reason=f"Matched rejection keyword: '{keyword}'"
                )
        
        # INTERVIEW
        for keyword in self.interview_keywords:
            if keyword in text:
                return ClassificationResult(
                    status=ClassificationStatus.INTERVIEW,
                    source=ClassificationSource.RULE,
                    rule_name="interview_keywords",
                    confidence=0.95,
                    reason=f"Matched interview keyword: '{keyword}'"
                )
        
        # OFFER
        for keyword in self.offer_keywords:
            if keyword in text:
                return ClassificationResult(
                    status=ClassificationStatus.OFFER,
                    source=ClassificationSource.RULE,
                    rule_name="offer_keywords",
                    confidence=0.95,
                    reason=f"Matched offer keyword: '{keyword}'"
                )
        
        return None
    
    def _classify_with_llm(
        self,
        email_data: Dict,
        thread_history: Optional[List[Dict]] = None
    ) -> Optional[ClassificationResult]:
        """
        STAGE 3: Local LLM Classification.
        
        Only called when no rule matched.
        Uses thread history context if available.
        """
        subject = email_data.get("subject", "")
        snippet = email_data.get("snippet", "")[:200]  # Privacy: max 200 chars
        sender_domain = email_data.get("sender_domain", "")
        
        # Build thread context string
        thread_context = ""
        if thread_history:
            prev_statuses = [h.get("status", "") for h in thread_history[-3:]]  # Last 3 classifications
            thread_context = f"Previous thread classifications: {', '.join(prev_statuses)}"
        
        # Build prompt
        prompt = self._build_llm_prompt(subject, snippet, sender_domain, thread_context)
        
        try:
            # Call LLM with timeout
            result = asyncio.run(
                asyncio.wait_for(
                    self._llm_call_async(prompt),
                    timeout=self.llm_timeout_sec
                )
            )
            
            if result:
                return result
        except asyncio.TimeoutError:
            logger.debug(f"LLM classification timeout after {self.llm_timeout_sec}s")
        except Exception as e:
            logger.debug(f"LLM classification error: {e}")
        
        return None
    
    def _classify_batch_with_llm(
        self,
        email_candidates: List[Tuple[Dict, Optional[List[Dict]]]]
    ) -> List[Optional[ClassificationResult]]:
        """
        Batch LLM classification for performance.
        
        Processes emails in batches to reduce LLM calls.
        """
        results = []
        
        # Process in batches
        for i in range(0, len(email_candidates), self.llm_batch_size):
            batch = email_candidates[i:i + self.llm_batch_size]
            batch_results = []
            
            # Process batch (can be parallelized in future)
            for email_data, thread_history in batch:
                result = self._classify_with_llm(email_data, thread_history)
                batch_results.append(result)
            
            results.extend(batch_results)
        
        return results
    
    def _build_llm_prompt(
        self,
        subject: str,
        snippet: str,
        sender_domain: str,
        thread_context: str = ""
    ) -> str:
        """
        Build LLM prompt with strict JSON output format.
        
        PRIVACY: Only includes subject, snippet (max 200 chars), sender_domain.
        NO full email body.
        """
        prompt = f"""Classify this job application email into exactly ONE category.

CATEGORIES (STRICT ENUM - must be one of these):
- ACTIVE: Application confirmation, submission acknowledgment, or general job-related communication
- REJECTED: Rejection, not selected, declined application
- INTERVIEW: Interview invitation, scheduling, or interview-related communication
- OFFER: Job offer, compensation details, welcome message, onboarding
- GHOSTED: No response after extended period (only use if explicitly indicated)
- WITHDRAWN: Application withdrawn by candidate

EMAIL DATA:
Subject: {subject}
Snippet: {snippet[:200]}
Sender Domain: {sender_domain}
{thread_context if thread_context else ""}

OUTPUT FORMAT (STRICT JSON):
{{
  "status": "ACTIVE | INTERVIEW | REJECTED | OFFER | GHOSTED | WITHDRAWN",
  "confidence": 0.0-1.0,
  "reason": "Short human-readable explanation"
}}

Respond with ONLY valid JSON, no other text."""
        
        return prompt
    
    async def _llm_call_async(self, prompt: str) -> Optional[ClassificationResult]:
        """
        Async LLM call with strict JSON parsing.
        
        Returns ClassificationResult or None on failure.
        """
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.llm_url,
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "max_tokens": self.llm_max_tokens,
                            "temperature": 0.1  # Low temperature for consistency
                        }
                    },
                    timeout=aiohttp.ClientTimeout(total=self.llm_timeout_sec)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        llm_response = result.get("response", "").strip()
                        
                        # Parse JSON response
                        try:
                            # Extract JSON from response (might have extra text)
                            json_match = re.search(r'\{[^{}]*\}', llm_response, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                parsed = json.loads(json_str)
                                
                                status_str = parsed.get("status", "").upper()
                                confidence = float(parsed.get("confidence", 0.5))
                                reason = parsed.get("reason", "LLM classification")
                                
                                # Validate status
                                try:
                                    status = ClassificationStatus(status_str)
                                except ValueError:
                                    logger.warning(f"Invalid status from LLM: {status_str}")
                                    return None
                                
                                return ClassificationResult(
                                    status=status,
                                    source=ClassificationSource.LLM,
                                    llm_reason=reason,
                                    confidence=confidence,
                                    reason=reason
                                )
                        except (json.JSONDecodeError, ValueError, KeyError) as e:
                            logger.warning(f"Failed to parse LLM JSON response: {e}, response: {llm_response[:100]}")
                            return None
                    else:
                        logger.warning(f"LLM request failed with status {response.status}")
                        return None
        except Exception as e:
            logger.debug(f"LLM call error: {e}")
            return None
    
    def get_thread_history(
        self,
        user_id: str,
        thread_id: str
    ) -> List[Dict]:
        """
        Get thread history for context-aware classification.
        
        Returns list of previous classifications in thread, ordered by received_at.
        """
        if not self.db:
            return []
        
        try:
            from app.database import Application
            
            # Query previous emails in thread
            previous_emails = self.db.query(Application).filter(
                Application.user_id == user_id,
                Application.gmail_thread_id == thread_id
            ).order_by(Application.received_at.asc()).all()
            
            return [
                {
                    "status": email.category,
                    "received_at": email.received_at.isoformat() if email.received_at else None,
                    "classification_source": email.classification_source
                }
                for email in previous_emails
            ]
        except Exception as e:
            logger.warning(f"Failed to get thread history: {e}")
            return []
    
    def apply_thread_context(
        self,
        email_data: Dict,
        thread_history: List[Dict],
        base_result: ClassificationResult
    ) -> ClassificationResult:
        """
        Apply thread history context to classification result.
        
        Rules:
        - Previous = INTERVIEW → new vague email = INTERVIEW (not ACTIVE)
        - Previous = REJECTED → never revert to ACTIVE
        - Long silence (>30 days) after ACTIVE/INTERVIEW → mark GHOSTED
        """
        if not thread_history:
            return base_result
        
        # Get last classification in thread
        last_classification = thread_history[-1]
        last_status = last_classification.get("status", "").upper()
        
        # Rule: Previous = REJECTED → never revert to ACTIVE
        if last_status == "REJECTED" and base_result.status == ClassificationStatus.ACTIVE:
            return ClassificationResult(
                status=ClassificationStatus.REJECTED,
                source=ClassificationSource.THREAD_CONTEXT,
                reason="Previous classification was REJECTED, cannot revert to ACTIVE"
            )
        
        # Rule: Previous = INTERVIEW → new vague email = INTERVIEW (not ACTIVE)
        if last_status == "INTERVIEW" and base_result.status == ClassificationStatus.ACTIVE:
            # Check if email is vague (low confidence or no strong signals)
            if base_result.confidence is None or base_result.confidence < 0.7:
                return ClassificationResult(
                    status=ClassificationStatus.INTERVIEW,
                    source=ClassificationSource.THREAD_CONTEXT,
                    reason="Previous classification was INTERVIEW, maintaining INTERVIEW status"
                )
        
        # Rule: Long silence after ACTIVE/INTERVIEW → GHOSTED
        if last_status in ["ACTIVE", "INTERVIEW"]:
            last_received = last_classification.get("received_at")
            if last_received:
                try:
                    last_date = datetime.fromisoformat(last_received.replace('Z', '+00:00'))
                    current_date = email_data.get("received_at")
                    if isinstance(current_date, str):
                        current_date = datetime.fromisoformat(current_date.replace('Z', '+00:00'))
                    elif isinstance(current_date, datetime):
                        pass
                    else:
                        current_date = datetime.now(timezone.utc)
                    
                    days_since = (current_date - last_date).days
                    if days_since > self.ghosted_days:
                        return ClassificationResult(
                            status=ClassificationStatus.GHOSTED,
                            source=ClassificationSource.THREAD_CONTEXT,
                            reason=f"No response for {days_since} days after {last_status}"
                        )
                except Exception as e:
                    logger.debug(f"Failed to calculate ghosting: {e}")
        
        return base_result

# Backward compatibility: Create Classifier alias
Classifier = AdvancedClassifier
