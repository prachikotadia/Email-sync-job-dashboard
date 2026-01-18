from typing import Dict
import logging

logger = logging.getLogger(__name__)

class Classifier:
    """
    Two-stage classification pipeline
    Stage 2: High Precision - Strict classification
    Only 5 categories: Applied, Rejected, Interview, Offer/Accepted, Ghosted.
    Ghosted is set by time-based logic (ghosted_detector), not keywords.
    Returns exactly ONE of: applied, rejected, interview, offer, or "skip".
    """

    def __init__(self):
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

        logger.debug(f"Uncertain classification for: {subject[:50]}")
        return "skip"
