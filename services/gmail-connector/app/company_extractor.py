import re
from typing import Optional

class CompanyExtractor:
    """
    Multi-layer company name extraction
    Robust extraction with fallbacks
    """
    
    def __init__(self):
        # Known ATS domains and their company mappings
        self.ats_mappings = {
            'greenhouse.io': 'Greenhouse',
            'lever.co': 'Lever',
            'workday.com': 'Workday',
            'smartrecruiters.com': 'SmartRecruiters',
            'jobvite.com': 'Jobvite',
            'icims.com': 'iCIMS',
            'taleo.net': 'Taleo',
            'brassring.com': 'BrassRing',
        }
        
        # Common email providers to ignore
        self.ignore_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'icloud.com', 'aol.com', 'mail.com', 'protonmail.com'
        }
    
    def extract(self, subject: str, from_email: str, snippet: str) -> Optional[str]:
        """
        Multi-layer company extraction
        Returns normalized company name or None
        """
        # Layer 1: Check ATS domains
        company = self._extract_from_ats_domain(from_email)
        if company:
            return company
        
        # Layer 2: Extract from email domain
        company = self._extract_from_domain(from_email)
        if company:
            return company
        
        # Layer 3: Extract from signature/email content
        company = self._extract_from_signature(snippet)
        if company:
            return company
        
        # Layer 4: Extract from subject
        company = self._extract_from_subject(subject)
        if company:
            return company
        
        # Layer 5: Fallback to sender name
        company = self._extract_from_sender_name(from_email)
        if company:
            return company
        
        return None
    
    def _extract_from_ats_domain(self, from_email: str) -> Optional[str]:
        """Check if email is from known ATS"""
        from_email_lower = from_email.lower()
        for domain, company in self.ats_mappings.items():
            if domain in from_email_lower:
                # Try to extract actual company name from email
                # Format: company@greenhouse.io or noreply@company.greenhouse.io
                parts = from_email_lower.split('@')
                if len(parts) == 2:
                    local_part = parts[0]
                    domain_part = parts[1]
                    
                    # Check for company.greenhouse.io format
                    if '.' in domain_part:
                        domain_parts = domain_part.split('.')
                        if len(domain_parts) >= 2:
                            potential_company = domain_parts[0]
                            if potential_company not in ['noreply', 'no-reply', 'jobs', 'careers']:
                                return self._normalize(potential_company)
                
                # Fallback to ATS name
                return company
        return None
    
    def _extract_from_domain(self, from_email: str) -> Optional[str]:
        """Extract company from email domain"""
        if '@' not in from_email:
            return None
        
        domain = from_email.split('@')[1].lower()
        
        # Ignore common email providers
        if domain in self.ignore_domains:
            return None
        
        # Extract company name from domain
        # Remove common suffixes
        domain = domain.replace('.com', '').replace('.net', '').replace('.org', '')
        domain = domain.replace('.io', '').replace('.co', '').replace('.ai', '')
        
        # Split by dots and take first meaningful part
        parts = domain.split('.')
        company = parts[0] if parts else domain
        
        # Filter out common non-company words
        if company in ['mail', 'email', 'noreply', 'no-reply', 'jobs', 'careers', 'hiring']:
            if len(parts) > 1:
                company = parts[1]
            else:
                return None
        
        return self._normalize(company)
    
    def _extract_from_signature(self, snippet: str) -> Optional[str]:
        """Extract company from email signature"""
        if not snippet:
            return None
        
        # Look for patterns like "Company Name" or "| Company Name"
        patterns = [
            r'\|\s*([A-Z][a-zA-Z\s&]+)',
            r'@\s*([A-Z][a-zA-Z\s&]+)',
            r'Company:\s*([A-Z][a-zA-Z\s&]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, snippet)
            if match:
                company = match.group(1).strip()
                return self._normalize(company)
        
        return None
    
    def _extract_from_subject(self, subject: str) -> Optional[str]:
        """Extract company from subject line"""
        if not subject:
            return None
        
        # Patterns like "Re: Application at Company Name"
        patterns = [
            r'at\s+([A-Z][a-zA-Z\s&]+)',
            r'with\s+([A-Z][a-zA-Z\s&]+)',
            r'from\s+([A-Z][a-zA-Z\s&]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # Remove common trailing words
                company = re.sub(r'\s+(Inc|LLC|Ltd|Corp|Corporation)$', '', company, flags=re.IGNORECASE)
                return self._normalize(company)
        
        return None
    
    def _extract_from_sender_name(self, from_email: str) -> Optional[str]:
        """Fallback: Extract from sender name"""
        # Format: "Company Name <email@domain.com>" or "Name <email@domain.com>"
        if '<' in from_email and '>' in from_email:
            name_part = from_email.split('<')[0].strip()
            # Remove quotes
            name_part = name_part.replace('"', '').replace("'", '')
            
            # If it looks like a company name (capitalized, no @)
            if name_part and '@' not in name_part and name_part[0].isupper():
                return self._normalize(name_part)
        
        return None
    
    def _normalize(self, company: str) -> str:
        """
        Normalize company name
        Remove common words, capitalize properly
        """
        if not company:
            return None
        
        company = company.strip()
        
        # Remove common prefixes/suffixes
        company = re.sub(r'^(Careers|Jobs|Hiring|Recruiting|Talent)\s+', '', company, flags=re.IGNORECASE)
        company = re.sub(r'\s+(Careers|Jobs|Hiring|Recruiting|Talent)$', '', company, flags=re.IGNORECASE)
        
        # Capitalize properly
        words = company.split()
        normalized_words = []
        for word in words:
            if word.lower() in ['and', 'of', 'the', 'at', 'in', 'on']:
                normalized_words.append(word.lower())
            else:
                normalized_words.append(word.capitalize())
        
        company = ' '.join(normalized_words)
        
        return company
    
    def extract_role(self, subject: str, snippet: str) -> Optional[str]:
        """Extract job role from subject or snippet"""
        text = f"{subject} {snippet}".lower()
        
        # Common role keywords
        roles = [
            'software engineer', 'software developer', 'backend engineer', 'frontend engineer',
            'full stack engineer', 'data engineer', 'devops engineer', 'sre',
            'product manager', 'project manager', 'engineering manager',
            'data scientist', 'machine learning engineer', 'ml engineer',
            'designer', 'ui/ux designer', 'product designer',
            'analyst', 'data analyst', 'business analyst',
            'intern', 'internship'
        ]
        
        for role in roles:
            if role in text:
                # Capitalize properly
                return ' '.join(word.capitalize() for word in role.split())
        
        return None
