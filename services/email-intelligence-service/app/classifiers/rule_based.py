"""
Phase 1: Rule-Based Email Classifier

Deterministic keyword-based classifier that uses keyword matching
to classify emails into job application statuses.
"""
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from app.classifiers.keywords import KEYWORDS, CATEGORY_PRIORITY, CATEGORY_ALIASES
from app.classifiers.email_processor import extract_email_text, extract_email_metadata

logger = logging.getLogger(__name__)

# Hard exclusion patterns - emails matching these should NOT be stored
# Excludes: Newsletters, promos, marketing, coupons, job alerts, generic HR content,
# career advice, webinars, events, and ANY email without specific application intent
EXCLUSION_PATTERNS = [
    # Job alerts and recommendations
    "job alert", "jobs you may like", "jobs you might like", "recommended jobs",
    "top jobs", "recommended", "new jobs", "job opportunities", "job matches",
    "job suggestions", "similar jobs",
    # Newsletters and digests
    "digest", "newsletter", "weekly digest", "daily digest", "monthly digest",
    "email digest", "linkedin digest", "indeed alert", "glassdoor alert",
    "monster alert", "ziprecruiter alert",
    # Marketing and promotions
    "unsubscribe", "promo", "promotion", "coupon", "discount", "sale",
    "special offer", "limited time", "marketing",
    # Generic career content (not tied to specific application)
    "career advice", "career tips", "career guidance", "career webinar",
    "webinar", "event", "workshop", "seminar", "conference", "networking event",
    "career fair",
    # Generic HR content
    "hr newsletter", "talent newsletter", "recruiting newsletter", "hiring newsletter",
    # Ambiguous patterns
    "update your profile", "complete your profile", "profile reminder",
    "account update", "settings update",
]


class RuleBasedClassifier:
    """
    Rule-based email classifier using keyword matching.
    
    Features:
    - Keyword matching with weights
    - Category dominance rules
    - Confidence scoring
    - Explainable results
    """
    
    def __init__(self, ghosted_threshold_days: int = 14):
        """
        Initialize classifier.
        
        Args:
            ghosted_threshold_days: Days without response to mark as Ghosted
        """
        self.ghosted_threshold_days = ghosted_threshold_days
        self.keywords = KEYWORDS
        self.category_priority = CATEGORY_PRIORITY
        
    def classify(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify an email into one of the status categories.
        
        Args:
            email_data: Email data from Gmail API (format='full')
            
        Returns:
            Dict with:
            - predicted_status: One of ["Applied", "Interview", "Rejected", "Ghosted", "Accepted/Offer"]
            - confidence_score: Float 0.0 to 1.0
            - matched_keywords: List of matched keywords
            - category_scores: Scores for each category
            - explanation: Human-readable explanation
        """
        try:
            # Extract and normalize email text
            text_data = extract_email_text(email_data)
            metadata = extract_email_metadata(email_data)
            
            combined_text = text_data["combined_text"]
            subject = text_data["subject"]
            body_text = text_data["body_text"]
            
            # HARD EXCLUSION CHECKS - instant discard before classification
            # ERR ON THE SIDE OF EXCLUDING: If ambiguous, DO NOT STORE IT
            combined_lower = combined_text.lower()
            for exclusion_pattern in EXCLUSION_PATTERNS:
                if exclusion_pattern.lower() in combined_lower:
                    logger.info(f"Email excluded: Contains exclusion pattern '{exclusion_pattern}'")
                    return {
                        "predicted_status": "Unknown",
                        "confidence_score": 0.0,
                        "matched_keywords": [],
                        "category_scores": {},
                        "explanation": f"Excluded: Contains '{exclusion_pattern}' (newsletter/marketing/alert/generic content). No specific application/interview/rejection/offer intent.",
                        "rule_based": True,
                        "excluded": True,
                    }
            
            # Check for List-Unsubscribe header (marketing/newsletter indicator)
            headers = email_data.get("payload", {}).get("headers", [])
            if isinstance(headers, list):
                for header in headers:
                    if isinstance(header, dict):
                        header_name = header.get("name", "").lower()
                        if header_name == "list-unsubscribe":
                            logger.info("Email excluded: Contains List-Unsubscribe header")
                            return {
                                "predicted_status": "Unknown",
                                "confidence_score": 0.0,
                                "matched_keywords": [],
                                "category_scores": {},
                                "explanation": "Excluded: Newsletter/marketing email (List-Unsubscribe header detected). No specific application intent.",
                                "rule_based": True,
                                "excluded": True,
                            }
            
            # Calculate scores for each category
            category_scores = {}
            matched_keywords_all = {}
            
            for category in ["Applied", "Interview", "Rejected", "Ghosted", "Accepted/Offer"]:
                score, matched = self._calculate_category_score(
                    category=category,
                    subject=subject,
                    body_text=body_text,
                    combined_text=combined_text
                )
                category_scores[category] = score
                matched_keywords_all[category] = matched
            
            # Apply dominance rules (higher priority categories win)
            # Find category with highest score
            best_category = max(category_scores.items(), key=lambda x: x[1])
            predicted_status = best_category[0]
            base_score = best_category[1]
            
            # Apply priority boost (higher priority categories get slight boost)
            priority_boost = self.category_priority.get(predicted_status, 0) / 1000.0
            confidence_score = min(1.0, base_score + priority_boost)
            
            # STRICT FILTERING: Only classify if we have reasonable confidence
            # ERR ON THE SIDE OF EXCLUDING: If ambiguous, DO NOT STORE IT
            # Increased threshold from 0.3 to 0.5 to be more strict
            if confidence_score < 0.5:
                predicted_status = "Unknown"
                confidence_score = base_score  # Keep original low score
                explanation = "Excluded: Low confidence - no strong keyword matches found. Email does not match any job application category. Ambiguous emails are excluded per strict filtering rules."
            else:
                # Additional check: Must have specific application intent
                # Even with high confidence, verify it's actually about an application
                application_intent_keywords = [
                    "application", "applied", "interview", "rejected", "offer",
                    "hiring", "recruiter", "candidate", "position", "role", "job"
                ]
                has_application_intent = any(
                    keyword in combined_text.lower() for keyword in application_intent_keywords
                )
                
                if not has_application_intent:
                    predicted_status = "Unknown"
                    confidence_score = 0.0
                    explanation = "Excluded: No specific application/interview/rejection/offer intent found. Generic HR content not tied to an application is excluded."
                else:
                    matched_keywords = matched_keywords_all.get(predicted_status, [])
                    explanation = self._generate_explanation(
                        predicted_status,
                        confidence_score,
                        matched_keywords,
                        category_scores
                    )
            
            # Get matched keywords for the predicted status (empty if Unknown)
            matched_keywords = []
            if predicted_status != "Unknown":
                matched_keywords = matched_keywords_all.get(predicted_status, [])
            
            return {
                "predicted_status": predicted_status,
                "confidence_score": confidence_score,
                "matched_keywords": matched_keywords,
                "category_scores": category_scores,
                "explanation": explanation,
                "rule_based": True,  # Indicates this is rule-based classification
            }
            
        except Exception as e:
            logger.error(f"Error classifying email: {e}", exc_info=True)
            # Return "Unknown" on error - will be filtered out
            return {
                "predicted_status": "Unknown",
                "confidence_score": 0.0,
                "matched_keywords": [],
                "category_scores": {},
                "explanation": f"Classification error: {str(e)}",
                "rule_based": True,
            }
    
    def _calculate_category_score(
        self,
        category: str,
        subject: str,
        body_text: str,
        combined_text: str
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calculate score for a category based on keyword matches.
        
        Args:
            category: Category to score
            subject: Normalized subject text
            body_text: Normalized body text
            combined_text: Combined subject + body
            
        Returns:
            Tuple of (score, matched_keywords)
        """
        if category not in self.keywords:
            return 0.0, []
        
        matched_keywords = []
        total_score = 0.0
        match_count = 0
        
        # Subject has higher weight (2x)
        subject_weight = 2.0
        body_weight = 1.0
        
        for keyword_data in self.keywords[category]:
            if not keyword_data.get("active", True):
                continue
            
            keyword = keyword_data["keyword"]
            weight = keyword_data.get("weight", 1.0)
            keyword_type = keyword_data.get("type", "partial")
            
            # Check subject
            subject_matches = self._match_keyword(keyword, subject, keyword_type)
            if subject_matches:
                matched_keywords.append({
                    "keyword": keyword,
                    "weight": weight,
                    "type": keyword_type,
                    "location": "subject",
                    "matches": subject_matches,
                })
                total_score += weight * subject_weight
                match_count += 1
            
            # Check body
            body_matches = self._match_keyword(keyword, body_text, keyword_type)
            if body_matches and not subject_matches:  # Don't double-count
                matched_keywords.append({
                    "keyword": keyword,
                    "weight": weight,
                    "type": keyword_type,
                    "location": "body",
                    "matches": body_matches,
                })
                total_score += weight * body_weight
                match_count += 1
        
        # Normalize score (max possible score for category)
        max_possible_score = sum(
            kw.get("weight", 1.0) * subject_weight
            for kw in self.keywords[category]
            if kw.get("active", True)
        )
        
        if max_possible_score > 0:
            normalized_score = min(1.0, total_score / max_possible_score)
        else:
            normalized_score = 0.0
        
        # Boost confidence if multiple matches
        if match_count > 1:
            normalized_score = min(1.0, normalized_score * (1 + 0.1 * (match_count - 1)))
        
        return normalized_score, matched_keywords
    
    def _match_keyword(self, keyword: str, text: str, keyword_type: str) -> int:
        """
        Match keyword in text based on type.
        
        Args:
            keyword: Keyword to match
            text: Text to search in
            keyword_type: Type of matching (exact, partial, regex)
            
        Returns:
            Number of matches found
        """
        if not text or not keyword:
            return 0
        
        if keyword_type == "exact":
            # Exact word match (case-insensitive)
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            matches = len(re.findall(pattern, text.lower()))
            return matches
        
        elif keyword_type == "partial":
            # Partial match (substring)
            return text.lower().count(keyword.lower())
        
        elif keyword_type == "regex":
            # Regex pattern
            try:
                pattern = re.compile(keyword, re.IGNORECASE)
                matches = len(pattern.findall(text))
                return matches
            except:
                return 0
        
        else:
            # Default to partial
            return text.lower().count(keyword.lower())
    
    def _generate_explanation(
        self,
        predicted_status: str,
        confidence_score: float,
        matched_keywords: List[Dict[str, Any]],
        category_scores: Dict[str, float]
    ) -> str:
        """
        Generate human-readable explanation for classification.
        """
        parts = []
        
        parts.append(f"Classified as '{predicted_status}' with {confidence_score:.1%} confidence.")
        
        if matched_keywords:
            keyword_list = [kw["keyword"] for kw in matched_keywords[:5]]  # Top 5
            parts.append(f"Matched keywords: {', '.join(keyword_list)}")
        
        # Show competing categories
        sorted_scores = sorted(
            category_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]  # Top 3
        
        if len(sorted_scores) > 1:
            other_categories = [
                f"{cat} ({score:.1%})" 
                for cat, score in sorted_scores[1:] 
                if score > 0.1
            ]
            if other_categories:
                parts.append(f"Other categories: {', '.join(other_categories)}")
        
        return " ".join(parts)
