import re
import logging
from typing import Optional, Tuple
from html import unescape
import base64

logger = logging.getLogger(__name__)

class CompanyExtractor:
    """
    Multi-layer company name extraction with strict rules
    Ensures company_name is NEVER empty or null
    """
    
    def __init__(self):
        # Known ATS domains - DO NOT return these as company names
        self.ats_domains = {
            'greenhouse.io', 'lever.co', 'workday.com', 'smartrecruiters.com',
            'jobvite.com', 'icims.com', 'taleo.net', 'brassring.com',
            'ashbyhq.com', 'bamboohr.com', 'recruitee.com', 'comeet.com',
            'recruiterbox.com', 'zoho.com', 'breezy.hr', 'workable.com'
        }
        
        # Common email providers to ignore
        self.ignore_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'icloud.com', 'aol.com', 'mail.com', 'protonmail.com',
            'zoho.com', 'gmx.com', 'yandex.com', 'mail.ru'
        }
        
        # Common prefixes/suffixes to remove
        self.company_suffixes = ['LLC', 'Inc', 'Inc.', 'Ltd', 'Ltd.', 'Corp', 'Corporation', 
                                 'Pvt', 'Pvt.', 'Limited', 'Co', 'Co.']
        self.company_prefixes = ['Careers', 'Jobs', 'Hiring', 'Recruiting', 'Talent', 'HR']
    
    def extract(self, message: dict, subject: str, from_email: str, snippet: str) -> Tuple[str, str, float]:
        """
        Multi-layer company extraction with logging
        Returns: (company_name, source, confidence)
        company_name is NEVER None - always returns a valid string
        """
        email_id = message.get('id', 'unknown')
        
        # Layer 1: ATS → Company mapping (HIGHEST PRIORITY)
        company, source, confidence = self._extract_from_ats(message, from_email, email_id)
        if company and confidence >= 0.8:
            logger.info(f"[CompanyExtract] email_id={email_id} source={source} company={company} confidence={confidence:.2f}")
            return company, source, confidence
        
        # Layer 2: Email domain analysis
        company, source, confidence = self._extract_from_domain(from_email, email_id)
        if company and confidence >= 0.7:
            logger.info(f"[CompanyExtract] email_id={email_id} source={source} company={company} confidence={confidence:.2f}")
            return company, source, confidence
        
        # Layer 3: Subject line NLP
        company, source, confidence = self._extract_from_subject(subject, email_id)
        if company and confidence >= 0.6:
            logger.info(f"[CompanyExtract] email_id={email_id} source={source} company={company} confidence={confidence:.2f}")
            return company, source, confidence
        
        # Layer 4: Email signature parsing
        company, source, confidence = self._extract_from_signature(snippet, email_id)
        if company and confidence >= 0.5:
            logger.info(f"[CompanyExtract] email_id={email_id} source={source} company={company} confidence={confidence:.2f}")
            return company, source, confidence
        
        # Layer 5: Fallback (LAST RESORT - NEVER returns None)
        company, source, confidence = self._extract_fallback(from_email, email_id)
        logger.warning(f"[CompanyExtract] email_id={email_id} source={source} company={company} confidence={confidence:.2f} (FALLBACK USED)")
        return company, source, confidence
    
    def _extract_from_ats(self, message: dict, from_email: str, email_id: str) -> Tuple[Optional[str], str, float]:
        """
        Layer 1: Extract company from ATS emails by parsing HTML body
        """
        from_email_lower = from_email.lower()
        
        # Detect ATS domain
        ats_detected = None
        for ats_domain in self.ats_domains:
            if ats_domain in from_email_lower:
                ats_detected = ats_domain
                break
        
        if not ats_detected:
            return None, "ATS", 0.0
        
        # Try to extract company from email domain first (e.g., company.greenhouse.io)
        domain_parts = from_email_lower.split('@')
        if len(domain_parts) == 2:
            domain = domain_parts[1]
            # Check for company.greenhouse.io format
            if '.' in domain:
                parts = domain.split('.')
                if len(parts) >= 3:  # company.greenhouse.io
                    potential_company = parts[0]
                    if potential_company not in ['noreply', 'no-reply', 'jobs', 'careers', 'hiring', 'notifications']:
                        normalized = self._normalize(potential_company)
                        if normalized and normalized.lower() not in ['mail', 'email']:
                            return normalized, "ATS_DOMAIN", 0.85
        
        # Parse email body HTML to find actual company name
        html_body = self._extract_html_body(message)
        if html_body:
            # Look for common ATS patterns in HTML
            patterns = [
                r'thank\s+you\s+for\s+applying\s+to\s+([A-Z][a-zA-Z\s&]+)',
                r'your\s+application\s+at\s+([A-Z][a-zA-Z\s&]+)',
                r'application\s+to\s+([A-Z][a-zA-Z\s&]+)',
                r'position\s+at\s+([A-Z][a-zA-Z\s&]+)',
                r'role\s+at\s+([A-Z][a-zA-Z\s&]+)',
                r'alt=["\']([A-Z][a-zA-Z\s&]+)\s+(Logo|Careers|Jobs)["\']',
                r'<title>([A-Z][a-zA-Z\s&]+)\s+(Careers|Jobs|Hiring)</title>',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, html_body, re.IGNORECASE)
                for match in matches:
                    company = match.group(1).strip()
                    # Clean up HTML entities
                    company = unescape(company)
                    # Remove common trailing words
                    company = re.sub(r'\s+(Inc|LLC|Ltd|Corp|Corporation|Careers|Jobs|Hiring)$', '', company, flags=re.IGNORECASE)
                    if len(company) > 2 and company.lower() not in ['the', 'and', 'for', 'with']:
                        normalized = self._normalize(company)
                        if normalized:
                            return normalized, "ATS_HTML", 0.9
        
        # Last resort: try to extract from sender display name
        if '<' in from_email and '>' in from_email:
            name_part = from_email.split('<')[0].strip().strip('"').strip("'")
            if name_part and '@' not in name_part:
                normalized = self._normalize(name_part)
                if normalized:
                    return normalized, "ATS_SENDER", 0.6
        
        return None, "ATS", 0.0
    
    def _extract_html_body(self, message: dict) -> Optional[str]:
        """Extract HTML body from Gmail message payload"""
        try:
            payload = message.get('payload', {})
            
            def extract_from_part(part):
                """Recursively extract HTML from message parts"""
                if part.get('mimeType') == 'text/html':
                    data = part.get('body', {}).get('data')
                    if data:
                        try:
                            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        except:
                            return None
                
                # Check multipart
                if part.get('mimeType') == 'multipart/alternative' or part.get('mimeType') == 'multipart/mixed':
                    parts = part.get('parts', [])
                    for subpart in parts:
                        html = extract_from_part(subpart)
                        if html:
                            return html
                
                return None
            
            return extract_from_part(payload)
        except Exception as e:
            logger.debug(f"Error extracting HTML body: {e}")
            return None
    
    def _extract_from_domain(self, from_email: str, email_id: str) -> Tuple[Optional[str], str, float]:
        """
        Layer 2: Extract company from email domain
        """
        if '@' not in from_email:
            return None, "DOMAIN", 0.0
        
        domain = from_email.split('@')[1].lower()
        
        # Ignore common email providers
        if domain in self.ignore_domains:
            return None, "DOMAIN", 0.0
        
        # Ignore ATS domains (should be caught in Layer 1, but double-check)
        if any(ats in domain for ats in self.ats_domains):
            return None, "DOMAIN", 0.0
        
        # Extract domain name (remove TLD)
        domain_parts = domain.split('.')
        if not domain_parts:
            return None, "DOMAIN", 0.0
        
        # Remove common prefixes from local part
        local_part = from_email.split('@')[0].lower()
        if local_part in ['noreply', 'no-reply', 'jobs', 'careers', 'hiring', 'notifications', 'mail', 'email']:
            # Use domain name
            company = domain_parts[0]
        else:
            # Try local part first (e.g., hiring@stripe.com -> stripe)
            if local_part not in ['noreply', 'no-reply', 'jobs', 'careers', 'hiring']:
                company = local_part
            else:
                company = domain_parts[0]
        
        # Remove TLD from domain
        if len(domain_parts) > 1:
            company = domain_parts[0]
        
        # Filter out invalid companies
        if company in ['mail', 'email', 'www', 'www2', 'web', 'smtp']:
            if len(domain_parts) > 1:
                company = domain_parts[1]
            else:
                return None, "DOMAIN", 0.0
        
        normalized = self._normalize(company)
        if normalized:
            return normalized, "DOMAIN", 0.75
        
        return None, "DOMAIN", 0.0
    
    def _extract_from_subject(self, subject: str, email_id: str) -> Tuple[Optional[str], str, float]:
        """
        Layer 3: Extract company from subject line using NLP patterns
        """
        if not subject:
            return None, "SUBJECT", 0.0
        
        subject_lower = subject.lower()
        
        # Patterns to extract company from subject
        patterns = [
            r'application\s+to\s+([A-Z][a-zA-Z\s&]+)',
            r'application\s+at\s+([A-Z][a-zA-Z\s&]+)',
            r'your\s+application\s+to\s+([A-Z][a-zA-Z\s&]+)',
            r'your\s+application\s+at\s+([A-Z][a-zA-Z\s&]+)',
            r'interview\s+(?:invitation|request|scheduled)\s+(?:at|with|from)\s+([A-Z][a-zA-Z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\s+interview\s+invitation',
            r'update\s+(?:on|from)\s+(?:your\s+)?(?:application|interview)\s+(?:at|with|from)\s+([A-Z][a-zA-Z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\s+(?:careers|jobs|hiring)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, subject, re.IGNORECASE)
            for match in matches:
                company = match.group(1).strip()
                # Remove common trailing words
                company = re.sub(r'\s+(Inc|LLC|Ltd|Corp|Corporation|Careers|Jobs|Hiring|Application|Interview)$', 
                               '', company, flags=re.IGNORECASE)
                # Remove common leading words
                company = re.sub(r'^(Your|The|An|A)\s+', '', company, flags=re.IGNORECASE)
                
                if len(company) > 2 and company.lower() not in ['the', 'and', 'for', 'with', 'from', 'at']:
                    normalized = self._normalize(company)
                    if normalized:
                        return normalized, "SUBJECT", 0.65
        
        return None, "SUBJECT", 0.0
    
    def _extract_from_signature(self, snippet: str, email_id: str) -> Tuple[Optional[str], str, float]:
        """
        Layer 4: Extract company from email signature (last 15-20 lines)
        """
        if not snippet:
            return None, "SIGNATURE", 0.0
        
        # Take last portion of snippet (signature is usually at the end)
        lines = snippet.split('\n')
        signature_lines = lines[-20:] if len(lines) > 20 else lines
        signature_text = '\n'.join(signature_lines)
        
        # Patterns for signature extraction
        patterns = [
            r'([A-Z][a-zA-Z\s&]+),\s*(?:Recruiter|HR|Talent|Hiring)',
            r'(?:Recruiter|HR|Talent|Hiring),\s*([A-Z][a-zA-Z\s&]+)',
            r'at\s+([A-Z][a-zA-Z\s&]+)',
            r'@\s*([A-Z][a-zA-Z\s&]+)',
            r'\|\s*([A-Z][a-zA-Z\s&]+)',
            r'Company:\s*([A-Z][a-zA-Z\s&]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, signature_text, re.IGNORECASE)
            for match in matches:
                company = match.group(1).strip()
                # Remove common suffixes
                company = re.sub(r'\s+(Inc|LLC|Ltd|Corp|Corporation)$', '', company, flags=re.IGNORECASE)
                if len(company) > 2:
                    normalized = self._normalize(company)
                    if normalized:
                        return normalized, "SIGNATURE", 0.55
        
        return None, "SIGNATURE", 0.0
    
    def _extract_fallback(self, from_email: str, email_id: str) -> Tuple[str, str, float]:
        """
        Layer 5: Fallback - MUST return a valid company name (never None)
        """
        # Try sender display name
        if '<' in from_email and '>' in from_email:
            name_part = from_email.split('<')[0].strip().strip('"').strip("'")
            if name_part and '@' not in name_part and len(name_part) > 2:
                normalized = self._normalize(name_part)
                if normalized:
                    return normalized, "FALLBACK_SENDER", 0.4
        
        # Try domain as last resort
        if '@' in from_email:
            domain = from_email.split('@')[1].lower()
            domain_parts = domain.split('.')
            if domain_parts and domain_parts[0] not in self.ignore_domains:
                company = domain_parts[0]
                normalized = self._normalize(company)
                if normalized:
                    return normalized, "FALLBACK_DOMAIN", 0.3
        
        # Absolute last resort - but NEVER return None
        return "Unknown Company", "FALLBACK_UNKNOWN", 0.1
    
    def _normalize(self, company: str) -> Optional[str]:
        """
        Normalize company name - remove prefixes/suffixes, capitalize properly
        """
        if not company:
            return None
        
        company = company.strip()
        if not company:
            return None
        
        # Remove common prefixes
        for prefix in self.company_prefixes:
            company = re.sub(rf'^{prefix}\s+', '', company, flags=re.IGNORECASE)
            company = re.sub(rf'\s+{prefix}$', '', company, flags=re.IGNORECASE)
        
        # Remove common suffixes
        for suffix in self.company_suffixes:
            company = re.sub(rf'\s+{suffix}$', '', company, flags=re.IGNORECASE)
        
        company = company.strip()
        if not company or len(company) < 2:
            return None
        
        # Capitalize properly (Title Case)
        words = company.split()
        normalized_words = []
        for word in words:
            # Handle special cases
            if word.lower() in ['and', 'of', 'the', 'at', 'in', 'on', 'for', 'with']:
                normalized_words.append(word.lower())
            elif word.upper() in ['LLC', 'INC', 'LTD', 'CORP']:
                normalized_words.append(word.upper())
            elif '-' in word:
                # Handle hyphenated words (e.g., "Co-Founder")
                parts = word.split('-')
                normalized_words.append('-'.join(p.capitalize() for p in parts))
            else:
                normalized_words.append(word.capitalize())
        
        company = ' '.join(normalized_words)
        
        # Final cleanup
        company = re.sub(r'\s+', ' ', company)  # Multiple spaces
        company = company.strip()
        
        return company if company else None
    
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
