"""
Machine Learning Model for Company Name Extraction
Trains on email patterns to accurately identify company names
"""
import re
import pickle
import os
from typing import Optional, Dict, List, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class CompanyNameModel:
    """
    ML-based company name extractor
    Uses pattern recognition and trained models to identify company names
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "/app/state/company_model.pkl"
        self.patterns = self._load_patterns()
        self.company_db = self._load_company_database()
        
    def _load_patterns(self) -> Dict[str, List[str]]:
        """Load regex patterns for company name extraction"""
        return {
            'ats_patterns': [
                r'([a-zA-Z0-9-]+)\.greenhouse\.io',
                r'([a-zA-Z0-9-]+)\.lever\.co',
                r'([a-zA-Z0-9-]+)\.workday\.com',
                r'([a-zA-Z0-9-]+)\.smartrecruiters\.com',
                r'([a-zA-Z0-9-]+)\.jobvite\.com',
                r'([a-zA-Z0-9-]+)\.icims\.com',
            ],
            'email_patterns': [
                r'([a-zA-Z0-9-]+)@([a-zA-Z0-9.-]+)\.(com|io|co|net|org|ai)',
                r'noreply@([a-zA-Z0-9-]+)\.(com|io|co|net|org)',
                r'jobs@([a-zA-Z0-9-]+)\.(com|io|co|net|org)',
                r'careers@([a-zA-Z0-9-]+)\.(com|io|co|net|org)',
                r'hiring@([a-zA-Z0-9-]+)\.(com|io|co|net|org)',
            ],
            'subject_patterns': [
                r'(?:at|with|from|for)\s+([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
                r'Application\s+(?:at|with|from|for)\s+([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
                r'Interview\s+(?:at|with|from)\s+([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
                r'Offer\s+(?:from|at)\s+([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
            ],
            'signature_patterns': [
                r'\|\s*([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
                r'@\s*([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
                r'Company:\s*([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
                r'([A-Z][a-zA-Z0-9\s&.-]+?)\s+(?:Inc|LLC|Ltd|Corp|Corporation)',
            ]
        }
    
    def _load_company_database(self) -> Dict[str, str]:
        """Load known company name mappings"""
        # Common company name variations
        return {
            # Tech companies
            'google': 'Google',
            'microsoft': 'Microsoft',
            'apple': 'Apple',
            'amazon': 'Amazon',
            'meta': 'Meta',
            'facebook': 'Meta',
            'netflix': 'Netflix',
            'tesla': 'Tesla',
            'nvidia': 'NVIDIA',
            'intel': 'Intel',
            'amd': 'AMD',
            'oracle': 'Oracle',
            'salesforce': 'Salesforce',
            'adobe': 'Adobe',
            'ibm': 'IBM',
            'cisco': 'Cisco',
            'vmware': 'VMware',
            # ATS platforms
            'greenhouse': 'Greenhouse',
            'lever': 'Lever',
            'workday': 'Workday',
            'smartrecruiters': 'SmartRecruiters',
            'jobvite': 'Jobvite',
            'icims': 'iCIMS',
        }
    
    def extract(self, subject: str, from_email: str, snippet: str, body: Optional[str] = None) -> Optional[str]:
        """
        Extract company name using ML-based pattern matching
        Priority order:
        1. ATS domain extraction (highest confidence)
        2. Email domain extraction
        3. Subject line pattern matching
        4. Signature/body pattern matching
        5. Known company database lookup
        """
        # Normalize inputs
        subject = subject or ""
        from_email = from_email or ""
        snippet = snippet or ""
        body = body or ""
        combined_text = f"{subject} {snippet} {body}".lower()
        
        # Layer 1: ATS domain extraction (highest confidence)
        company = self._extract_from_ats(from_email)
        if company and self._is_valid_company(company):
            return self._normalize(company)
        
        # Layer 2: Email domain extraction
        company = self._extract_from_email_domain(from_email)
        if company and self._is_valid_company(company):
            return self._normalize(company)
        
        # Layer 3: Subject line pattern matching
        company = self._extract_from_subject(subject)
        if company and self._is_valid_company(company):
            return self._normalize(company)
        
        # Layer 4: Signature/body pattern matching
        company = self._extract_from_signature(snippet + " " + body)
        if company and self._is_valid_company(company):
            return self._normalize(company)
        
        # Layer 5: Known company database lookup
        company = self._lookup_company(combined_text)
        if company:
            return company
        
        return None
    
    def _extract_from_ats(self, from_email: str) -> Optional[str]:
        """Extract company from ATS domains"""
        from_email_lower = from_email.lower()
        
        for pattern in self.patterns['ats_patterns']:
            match = re.search(pattern, from_email_lower)
            if match:
                company = match.group(1)
                # Filter out common non-company words
                if company not in ['noreply', 'no-reply', 'jobs', 'careers', 'hiring', 'mail', 'email']:
                    return company
        
        return None
    
    def _extract_from_email_domain(self, from_email: str) -> Optional[str]:
        """Extract company from email domain"""
        if '@' not in from_email:
            return None
        
        domain = from_email.split('@')[1].lower()
        
        # Ignore common email providers
        ignore_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'icloud.com', 'aol.com', 'mail.com', 'protonmail.com',
            'proton.me', 'zoho.com', 'yandex.com'
        }
        
        if domain in ignore_domains:
            return None
        
        # Extract company name from domain
        for pattern in self.patterns['email_patterns']:
            match = re.search(pattern, from_email.lower())
            if match:
                company = match.group(1) if len(match.groups()) > 0 else None
                if company and company not in ['noreply', 'no-reply', 'jobs', 'careers', 'hiring']:
                    return company
        
        # Fallback: extract from domain directly
        domain_parts = domain.split('.')
        if len(domain_parts) >= 2:
            company = domain_parts[0]
            if company not in ['www', 'mail', 'email', 'noreply', 'jobs', 'careers']:
                return company
        
        return None
    
    def _extract_from_subject(self, subject: str) -> Optional[str]:
        """Extract company from subject line using patterns"""
        if not subject:
            return None
        
        for pattern in self.patterns['subject_patterns']:
            matches = re.finditer(pattern, subject, re.IGNORECASE)
            for match in matches:
                company = match.group(1).strip()
                # Clean up common trailing words
                company = re.sub(r'\s+(Inc|LLC|Ltd|Corp|Corporation|Company)$', '', company, flags=re.IGNORECASE)
                company = re.sub(r'\s+(at|with|from|for)$', '', company, flags=re.IGNORECASE)
                if len(company) > 2 and company[0].isupper():
                    return company
        
        return None
    
    def _extract_from_signature(self, text: str) -> Optional[str]:
        """Extract company from email signature/body"""
        if not text:
            return None
        
        for pattern in self.patterns['signature_patterns']:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                company = match.group(1).strip()
                # Clean up
                company = re.sub(r'\s+(Inc|LLC|Ltd|Corp|Corporation)$', '', company, flags=re.IGNORECASE)
                if len(company) > 2 and company[0].isupper():
                    return company
        
        return None
    
    def _lookup_company(self, text: str) -> Optional[str]:
        """Lookup company in known database"""
        text_lower = text.lower()
        for key, value in self.company_db.items():
            if key in text_lower:
                return value
        return None
    
    def _is_valid_company(self, company: str) -> bool:
        """Validate if extracted string is likely a company name"""
        if not company or len(company) < 2:
            return False
        
        # Filter out common non-company words
        invalid_words = {
            'noreply', 'no-reply', 'jobs', 'careers', 'hiring', 'mail', 'email',
            'www', 'http', 'https', 'com', 'net', 'org', 'io', 'co', 'ai',
            'application', 'interview', 'offer', 'rejection', 'thank', 'you'
        }
        
        company_lower = company.lower()
        if company_lower in invalid_words:
            return False
        
        # Check if it looks like a company name (has letters, not just numbers)
        if not re.search(r'[a-zA-Z]', company):
            return False
        
        return True
    
    def _normalize(self, company: str) -> str:
        """Normalize company name"""
        if not company:
            return None
        
        company = company.strip()
        
        # Remove common prefixes/suffixes
        company = re.sub(r'^(Careers|Jobs|Hiring|Recruiting|Talent|Team)\s+', '', company, flags=re.IGNORECASE)
        company = re.sub(r'\s+(Careers|Jobs|Hiring|Recruiting|Talent|Team)$', '', company, flags=re.IGNORECASE)
        
        # Capitalize properly (Title Case)
        words = company.split()
        normalized_words = []
        for word in words:
            # Keep acronyms uppercase
            if word.isupper() and len(word) > 1:
                normalized_words.append(word)
            # Capitalize first letter of each word
            elif word:
                normalized_words.append(word.capitalize())
        
        company = ' '.join(normalized_words)
        
        # Check known database for exact match
        company_lower = company.lower()
        if company_lower in self.company_db:
            return self.company_db[company_lower]
        
        return company
    
    def train_from_data(self, training_data: List[Dict[str, str]]):
        """
        Train model from existing application data
        training_data: List of dicts with keys: 'subject', 'from_email', 'snippet', 'company_name'
        """
        logger.info(f"Training company name model on {len(training_data)} examples")
        
        # Extract patterns from training data
        patterns_found = {
            'ats_domains': Counter(),
            'email_domains': Counter(),
            'subject_patterns': Counter(),
        }
        
        for example in training_data:
            company = example.get('company_name', '').lower()
            from_email = example.get('from_email', '').lower()
            subject = example.get('subject', '').lower()
            
            # Learn ATS patterns
            for ats in ['greenhouse', 'lever', 'workday', 'smartrecruiters']:
                if ats in from_email:
                    patterns_found['ats_domains'][company] += 1
            
            # Learn email domain patterns
            if '@' in from_email:
                domain = from_email.split('@')[1]
                if domain not in ['gmail.com', 'yahoo.com', 'outlook.com']:
                    patterns_found['email_domains'][company] += 1
        
        # Update company database with learned patterns
        for company, count in patterns_found['ats_domains'].most_common(100):
            if count >= 2:  # At least 2 occurrences
                self.company_db[company] = company.title()
        
        logger.info(f"Learned {len(self.company_db)} company name patterns")
        
        # Save model
        self._save_model()
    
    def _save_model(self):
        """Save trained model to disk"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'company_db': self.company_db,
                    'patterns': self.patterns
                }, f)
            logger.info(f"Saved company model to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def _load_model(self):
        """Load trained model from disk"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.company_db.update(data.get('company_db', {}))
                    logger.info(f"Loaded company model from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load model: {e}, using defaults")
