from typing import Dict, Optional
import logging
import asyncio
import os

logger = logging.getLogger(__name__)

class Classifier:
    """
    Two-stage classification pipeline
    Stage 2: High Precision - Strict classification
    Only 5 categories: Applied, Rejected, Interview, Offer/Accepted, Ghosted.
    Ghosted is set by time-based logic (ghosted_detector), not keywords.
    Returns exactly ONE of: applied, rejected, interview, offer, or "skip".
    
    LOCAL LLM RESOURCE LIMITS:
    - Max tokens per email: 512 (configurable via LLM_MAX_TOKENS env var)
    - Timeout per inference: 2s (configurable via LLM_TIMEOUT_SEC env var)
    - Fallback: If LLM times out or fails → use rule-based classification only
    - LLM must NEVER block sync pipeline - always fallback on error/timeout
    
    SECURITY & PRIVACY GUARANTEE (CRITICAL):
    - Email content must NEVER be logged (no full email bodies in logs)
    - LLM prompts must NEVER include full email bodies
    - LLM prompts ONLY include:
      * Subject line (required for classification)
      * Snippet (first 200 characters max - truncated for privacy)
    - NO PII beyond subject + truncated snippet sent to LLM
    - NO email body content in any log statements
    - NO email body content in any database logs
    - Privacy is non-negotiable - email content stays private
    """

    def __init__(self):
        # LLM configuration with resource limits
        self.llm_enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
        self.llm_timeout_sec = float(os.getenv("LLM_TIMEOUT_SEC", "2.0"))  # Default 2s per email
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))  # Default 512 tokens per email
        self.llm_url = os.getenv("LLM_URL", "http://localhost:11434/api/generate")  # Ollama default
        
        self.keywords = {
            "applied": [
                "applied", "application", "submitted", "sent", "received your application"
            ],
            "rejected": [
                "rejected", "not selected", "unfortunately", "regret", "not moving forward",
                "decided to pursue other candidates", "not a fit", "declined"
            ],
            "interview": [
                "interview", "scheduling", "phone screen", "technical interview",
                "video interview", "onsite", "next steps", "interview process"
            ],
            # Offer / Accepted: one category (Offer)
            "offer": [
                "offer", "congratulations", "we'd like to offer", "we are pleased to offer",
                "job offer", "employment offer",
                "accepted", "looking forward", "excited to join", "welcome to the team",
                "onboarding", "start date"
            ],
        }

    def classify(self, application: Dict) -> str:
        """
        Stage 2: High Precision. Returns exactly ONE of: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, or "skip".
        Categories are UPPERCASE as per schema.
        Never assign multiple categories; never invent categories.
        
        RESOURCE LIMITS:
        - Tries LLM classification first (if enabled) with timeout
        - Falls back to rule-based if LLM times out or fails
        - LLM timeout: 2s per email (configurable)
        - Max tokens: 512 per email (configurable)
        """
        # Try LLM classification first (if enabled), with strict timeout and fallback
        if self.llm_enabled:
            try:
                llm_result = self._classify_with_llm_timeout(application)
                if llm_result and llm_result != "skip":
                    return llm_result
                # If LLM returns "skip" or None, fall through to rule-based
            except Exception as e:
                # LLM failed (timeout or error) - fallback to rule-based (NEVER block sync)
                logger.debug(f"LLM classification failed (fallback to rule-based): {e}")
        
        # Fallback to rule-based classification (always available, never blocks)
        return self._classify_rule_based(application)
    
    def _classify_rule_based(self, application: Dict) -> str:
        """
        Rule-based classification (fallback when LLM unavailable/timeout/fails).
        Never blocks - fast keyword matching.
        """
        subject = application.get("subject", "").lower()
        snippet = application.get("snippet", "").lower()
        text = f"{subject} {snippet}"

        # 1. Offer / Accepted (most specific) -> OFFER_ACCEPTED
        for keyword in self.keywords["offer"]:
            if keyword in text:
                return "OFFER_ACCEPTED"

        # 2. Rejected -> REJECTED
        for keyword in self.keywords["rejected"]:
            if keyword in text:
                return "REJECTED"

        # 3. Interview -> INTERVIEW
        for keyword in self.keywords["interview"]:
            if keyword in text:
                return "INTERVIEW"

        # 4. Applied -> APPLIED
        for keyword in self.keywords["applied"]:
            if keyword in text:
                return "APPLIED"

        # PRIVACY: Only log subject preview (first 50 chars), NEVER full email body
        logger.debug(f"Uncertain classification for: {subject[:50]}")
        return "skip"
    
    def _classify_with_llm_timeout(self, application: Dict) -> Optional[str]:
        """
        LLM classification with strict timeout and token limits.
        
        RESOURCE LIMITS:
        - Timeout: self.llm_timeout_sec (default 2s) per email
        - Max tokens: self.llm_max_tokens (default 512) per email
        - Returns None on timeout/error (triggers fallback)
        
        LLM must NEVER block sync pipeline - timeout is enforced strictly.
        """
        import aiohttp
        
        # Prepare text input (truncate to max tokens if needed)
        subject = application.get("subject", "")
        snippet = application.get("snippet", "")
        text = f"{subject} {snippet}"
        
        # Truncate text to prevent exceeding token limits (rough estimate: ~4 chars per token)
        max_chars = self.llm_max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.debug(f"Truncated text to {max_chars} chars (max tokens: {self.llm_max_tokens})")
        
        # Prepare LLM prompt
        # SECURITY & PRIVACY: ONLY subject + snippet (max 200 chars) - NO full email body
        # This is the ONLY place where email content is sent to LLM - strictly limited
        snippet_truncated = snippet[:200]  # Privacy: Only first 200 chars, no full body
        
        prompt = f"""Classify this job application email into exactly ONE category:
- APPLIED: Application confirmation/submission
- REJECTED: Rejection/not selected
- INTERVIEW: Interview invitation/scheduling
- OFFER_ACCEPTED: Offer letter or acceptance
- SKIP: Not job-related or uncertain

Email:
Subject: {subject}
Snippet: {snippet_truncated}

Respond with ONLY one word: APPLIED, REJECTED, INTERVIEW, OFFER_ACCEPTED, or SKIP."""

        async def _llm_call():
            """Async LLM call with timeout"""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.llm_url,
                        json={
                            "model": os.getenv("LLM_MODEL", "llama2"),  # Default model
                            "prompt": prompt,
                            "stream": False,
                            "options": {
                                "max_tokens": self.llm_max_tokens,
                                "temperature": 0.1  # Low temperature for consistent classification
                            }
                        },
                        timeout=aiohttp.ClientTimeout(total=self.llm_timeout_sec)
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            llm_response = result.get("response", "").strip().upper()
                            
                            # Parse LLM response - extract category
                            for category in ["APPLIED", "REJECTED", "INTERVIEW", "OFFER_ACCEPTED", "SKIP"]:
                                if category in llm_response:
                                    if category == "SKIP":
                                        return "skip"
                                    # Normalize OFFER_ACCEPTED
                                    if category == "OFFER":
                                        return "OFFER_ACCEPTED"
                                    return category
                            
                            # If no clear category, return None (fallback to rule-based)
                            logger.debug(f"LLM response unclear: {llm_response[:50]}")
                            return None
                        else:
                            logger.warning(f"LLM request failed with status {response.status}")
                            return None
            except asyncio.TimeoutError:
                logger.debug(f"LLM classification timeout after {self.llm_timeout_sec}s (fallback to rule-based)")
                return None
            except Exception as e:
                logger.debug(f"LLM classification error: {e} (fallback to rule-based)")
                return None
        
        # Run async LLM call with timeout (sync wrapper)
        try:
            # Use asyncio.run for sync context, but wrap in timeout
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running (async context), use create_task with timeout
                task = asyncio.create_task(_llm_call())
                return loop.run_until_complete(asyncio.wait_for(task, timeout=self.llm_timeout_sec))
            else:
                # No running loop - can use asyncio.run
                return loop.run_until_complete(asyncio.wait_for(_llm_call(), timeout=self.llm_timeout_sec))
        except asyncio.TimeoutError:
            logger.debug(f"LLM classification timeout after {self.llm_timeout_sec}s (fallback to rule-based)")
            return None
        except Exception as e:
            logger.debug(f"LLM classification error: {e} (fallback to rule-based)")
            return None