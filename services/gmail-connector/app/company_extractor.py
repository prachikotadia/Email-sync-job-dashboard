"""
Exact Company Name Extraction (Zero Weird Names)
Multi-signal extraction pipeline with confidence scoring
"""
import re
import yaml
import os
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Denylist - never accept these as company names
DENYLIST = {
    'recruiting', 'careers', 'hiring', 'team', 'talent', 'notifications',
    'noreply', 'no-reply', 'jobs', 'hr', 'human resources', 'applications',
    'notifications', 'updates', 'alerts', 'system', 'automated', 'mailer'
}

# Common email providers to ignore
EMAIL_PROVIDERS = {
    'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com',
    'aol.com', 'mail.com', 'protonmail.com', 'proton.me', 'zoho.com',
    'yandex.com', 'icloud.com', 'me.com', 'mac.com'
}

# Known ATS providers
ATS_PROVIDERS = {
    'greenhouse.io': 'greenhouse',
    'lever.co': 'lever',
    'workday.com': 'workday',
    'icims.com': 'icims',
    'smartrecruiters.com': 'smartrecruiters',
    'jobvite.com': 'jobvite',
    'ashbyhq.com': 'ashby',
    'taleo.net': 'taleo',
    'successfactors.com': 'successfactors',
    'brassring.com': 'brassring',
    'jobvite.com': 'jobvite',
    'icims.com': 'icims',
}

@dataclass
class ParsedEmail:
    """Parsed email structure"""
    from_email: str
    from_name: str
    reply_to_email: Optional[str]
    subject: str
    snippet: str
    headers: Dict[str, str]
    list_unsubscribe: Optional[str]
    body_text: str
    body_html: Optional[str]
    received_at: str
    message_id: str
    thread_id: str

@dataclass
class CompanyCandidate:
    """Company extraction candidate"""
    name: str
    score: int  # 0-100
    source: str  # DOMAIN, FROM_NAME, SIGNATURE, ATS_BRANDING, etc.
    evidence: str  # What text/pattern matched

@dataclass
class CompanyExtractionResult:
    """Final company extraction result"""
    company_name: str  # "Meta" or "Unknown"
    confidence: int    # 0-100
    source: str        # enum string
    ats_provider: Optional[str]
    candidates: List[Dict]  # List of CompanyCandidate as dicts

class CompanyExtractor:
    """
    Exact company name extraction with zero weird names
    Uses multi-signal pipeline with confidence scoring
    """
    
    def __init__(self):
        self.company_domains = self._load_company_domains()
        self.company_aliases = self._load_company_aliases()
        self.ats_extractors = {
            'greenhouse': self._extract_from_greenhouse,
            'lever': self._extract_from_lever,
            'ashby': self._extract_from_ashby,
            'workday': self._extract_from_workday,
        }
    
    def _load_company_domains(self) -> Dict[str, Dict]:
        """Load company domain mappings from YAML"""
        try:
            yaml_path = os.path.join(os.path.dirname(__file__), 'company_domains.yaml')
            if os.path.exists(yaml_path):
                with open(yaml_path, 'r') as f:
                    data = yaml.safe_load(f)
                    # Flatten structure
                    domains = {}
                    for domain, info in data.items():
                        domains[domain.lower()] = info.get('canonical', domain)
                        # Add aliases
                        for alias in info.get('aliases', []):
                            domains[alias.lower()] = info.get('canonical', domain)
                    return domains
        except Exception as e:
            logger.warning(f"Could not load company_domains.yaml: {e}")
        return {}
    
    def _load_company_aliases(self) -> Dict[str, str]:
        """Load company aliases from YAML"""
        try:
            yaml_path = os.path.join(os.path.dirname(__file__), 'company_aliases.yaml')
            if os.path.exists(yaml_path):
                with open(yaml_path, 'r') as f:
                    data = yaml.safe_load(f)
                    return {k.lower(): v for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Could not load company_aliases.yaml: {e}")
        return {}
    
    def extract_company_name(self, message: ParsedEmail, user_email: str) -> CompanyExtractionResult:
        """
        Main extraction function
        Returns CompanyExtractionResult with company_name, confidence, source, etc.
        """
        candidates = []
        
        # A) Direct domain mapping (highest priority)
        domain_candidates = self._extract_from_domain(message)
        candidates.extend(domain_candidates)
        
        # B) ATS provider detection + real company recovery
        ats_candidates, ats_provider = self._extract_from_ats(message)
        candidates.extend(ats_candidates)
        
        # C) From display name parsing (safe mode)
        from_name_candidates = self._extract_from_display_name(message)
        candidates.extend(from_name_candidates)
        
        # D) Signature-based extraction (very strict)
        signature_candidates = self._extract_from_signature(message)
        candidates.extend(signature_candidates)
        
        # E) ML/NER (optional, never sole authority)
        # Skipped for now - can be added later if needed
        
        # Select best candidate with safety rules
        result = self._select_best_candidate(candidates, ats_provider)
        
        return result
    
    def _extract_from_domain(self, message: ParsedEmail) -> List[CompanyCandidate]:
        """A) Direct domain mapping (highest priority)"""
        candidates = []
        
        # Check from_email domain
        domain = self._extract_domain(message.from_email)
        if domain:
            company = self._map_domain_to_company(domain)
            if company:
                score = 100 if domain in self.company_domains else 95
                candidates.append(CompanyCandidate(
                    name=company,
                    score=score,
                    source='DOMAIN',
                    evidence=f"Domain: {domain}"
                ))
        
        # Check reply_to_email domain as backup
        if message.reply_to_email:
            domain = self._extract_domain(message.reply_to_email)
            if domain:
                company = self._map_domain_to_company(domain)
                if company:
                    candidates.append(CompanyCandidate(
                        name=company,
                        score=90,  # Slightly lower than from_email
                        source='DOMAIN',
                        evidence=f"Reply-To domain: {domain}"
                    ))
        
        return candidates
    
    def _extract_from_ats(self, message: ParsedEmail) -> Tuple[List[CompanyCandidate], Optional[str]]:
        """B) ATS provider detection + real company recovery"""
        candidates = []
        ats_provider = None
        
        # Detect ATS by domain
        domain = self._extract_domain(message.from_email)
        if domain:
            for ats_domain, ats_name in ATS_PROVIDERS.items():
                if ats_domain in domain:
                    ats_provider = ats_name
                    break
        
        if not ats_provider:
            return candidates, None
        
        # Try to recover real company from ATS
        company = None
        score = 40  # Default low score for ATS-only
        
        # Try vendor-specific extractors
        if ats_provider in self.ats_extractors:
            company, evidence = self.ats_extractors[ats_provider](message)
            if company:
                score = 85  # Strong evidence from ATS link/pattern
                candidates.append(CompanyCandidate(
                    name=company,
                    score=score,
                    source='ATS_BRANDING',
                    evidence=evidence
                ))
        
        # Fallback: Try from_name patterns
        if not company:
            company, evidence = self._extract_company_from_ats_name(message.from_name)
            if company:
                score = 75
                candidates.append(CompanyCandidate(
                    name=company,
                    score=score,
                    source='ATS_BRANDING',
                    evidence=evidence
                ))
        
        # If no company found, return Unknown (don't use ATS provider name)
        if not company:
            # Return low-score Unknown candidate
            candidates.append(CompanyCandidate(
                name='Unknown',
                score=30,
                source='ATS_BRANDING',
                evidence=f"ATS detected ({ats_provider}) but no company found"
            ))
        
        return candidates, ats_provider
    
    def _extract_from_greenhouse(self, message: ParsedEmail) -> Tuple[Optional[str], str]:
        """Extract company from Greenhouse ATS"""
        # Look for boards.greenhouse.io/<slug>
        text = f"{message.body_text} {message.snippet} {message.subject}"
        
        pattern = r'boards\.greenhouse\.io/([a-zA-Z0-9-]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            slug = match.group(1)
            company = self._normalize_slug(slug)
            if company and company.lower() not in DENYLIST:
                return company, f"Greenhouse slug: {slug}"
        
        # Check unsubscribe URL
        if message.list_unsubscribe:
            pattern = r'greenhouse\.io/([a-zA-Z0-9-]+)'
            match = re.search(pattern, message.list_unsubscribe, re.IGNORECASE)
            if match:
                slug = match.group(1)
                company = self._normalize_slug(slug)
                if company and company.lower() not in DENYLIST:
                    return company, f"Greenhouse unsubscribe slug: {slug}"
        
        return None, ""
    
    def _extract_from_lever(self, message: ParsedEmail) -> Tuple[Optional[str], str]:
        """Extract company from Lever ATS"""
        text = f"{message.body_text} {message.snippet} {message.subject}"
        
        pattern = r'jobs\.lever\.co/([a-zA-Z0-9-]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            slug = match.group(1)
            company = self._normalize_slug(slug)
            if company and company.lower() not in DENYLIST:
                return company, f"Lever slug: {slug}"
        
        return None, ""
    
    def _extract_from_ashby(self, message: ParsedEmail) -> Tuple[Optional[str], str]:
        """Extract company from Ashby ATS"""
        text = f"{message.body_text} {message.snippet} {message.subject}"
        
        pattern = r'jobs\.ashbyhq\.com/([a-zA-Z0-9-]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            slug = match.group(1)
            company = self._normalize_slug(slug)
            if company and company.lower() not in DENYLIST:
                return company, f"Ashby slug: {slug}"
        
        return None, ""
    
    def _extract_from_workday(self, message: ParsedEmail) -> Tuple[Optional[str], str]:
        """Extract company from Workday ATS"""
        # Workday is harder - look for company name in subject/body patterns
        text = f"{message.subject} {message.snippet}"
        
        # Pattern: "Company - Application received"
        pattern = r'^([A-Z][a-zA-Z0-9\s&.-]+?)\s*-\s*(?:Application|Interview|Offer)'
        match = re.search(pattern, text)
        if match:
            company = match.group(1).strip()
            company = self._normalize_company(company)
            if company and company.lower() not in DENYLIST:
                return company, f"Workday subject pattern: {company}"
        
        return None, ""
    
    def _extract_company_from_ats_name(self, from_name: str) -> Tuple[Optional[str], str]:
        """Extract company from ATS from_name like 'Company via Greenhouse'"""
        if not from_name:
            return None, ""
        
        # Pattern: "Company via Greenhouse" or "Company - Greenhouse"
        patterns = [
            r'^([A-Z][a-zA-Z0-9\s&.-]+?)\s+via\s+(?:Greenhouse|Lever|Workday)',
            r'^([A-Z][a-zA-Z0-9\s&.-]+?)\s*-\s*(?:Greenhouse|Lever|Workday)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, from_name, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                company = self._normalize_company(company)
                if company and company.lower() not in DENYLIST:
                    return company, f"ATS from_name: {from_name}"
        
        return None, ""
    
    def _extract_from_display_name(self, message: ParsedEmail) -> List[CompanyCandidate]:
        """C) From display name parsing (safe mode)"""
        candidates = []
        
        if not message.from_name:
            return candidates
        
        # Remove junk tokens
        name = message.from_name
        for junk in ['no-reply', 'noreply', 'notifications', 'talent', 'recruiting', 'careers', 'jobs', 'team']:
            name = re.sub(rf'\b{re.escape(junk)}\b', '', name, flags=re.IGNORECASE)
        
        name = name.strip()
        
        # Reject if looks like person name (First Last pattern)
        if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', name):
            return candidates  # Likely a person, not company
        
        # Reject if too many words (>4) or contains job title words
        words = name.split()
        if len(words) > 4:
            return candidates
        
        job_title_words = ['manager', 'director', 'engineer', 'developer', 'recruiter', 'coordinator']
        if any(word.lower() in job_title_words for word in words):
            return candidates
        
        # Check if it's in denylist
        if name.lower() in DENYLIST:
            return candidates
        
        # If it looks like a company name (starts with capital, has org markers)
        if name and name[0].isupper() and len(name) > 2:
            company = self._normalize_company(name)
            if company and company.lower() not in DENYLIST:
                # Check if it matches known company
                if company.lower() in self.company_aliases:
                    company = self.company_aliases[company.lower()]
                
                score = 70 if len(words) <= 2 else 60
                candidates.append(CompanyCandidate(
                    name=company,
                    score=score,
                    source='FROM_NAME',
                    evidence=f"From name: {message.from_name}"
                ))
        
        return candidates
    
    def _extract_from_signature(self, message: ParsedEmail) -> List[CompanyCandidate]:
        """D) Signature-based extraction (very strict)"""
        candidates = []
        
        if not message.body_text:
            return candidates
        
        # Only look at last 30 lines
        lines = message.body_text.split('\n')
        signature_lines = lines[-30:] if len(lines) > 30 else lines
        signature_text = '\n'.join(signature_lines)
        
        # Patterns
        patterns = [
            r'Thanks?,\s*([A-Z][a-zA-Z0-9\s&.-]+?)\s+Recruiting',
            r'([A-Z][a-zA-Z0-9\s&.-]+?)\s+Talent\s+Acquisition',
            r'©\s*\d{4}\s+([A-Z][a-zA-Z0-9\s&.-]+?)(?:\s|$|,|\.)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, signature_text, re.IGNORECASE)
            for match in matches:
                company = match.group(1).strip()
                company = self._normalize_company(company)
                
                # Hard stoplist check
                if company and company.lower() not in DENYLIST:
                    # Check if it matches known company
                    if company.lower() in self.company_aliases:
                        company = self.company_aliases[company.lower()]
                    
                    candidates.append(CompanyCandidate(
                        name=company,
                        score=65,
                        source='SIGNATURE',
                        evidence=f"Signature pattern: {match.group(0)}"
                    ))
                    break  # Only take first match
        
        return candidates
    
    def _select_best_candidate(self, candidates: List[CompanyCandidate], ats_provider: Optional[str]) -> CompanyExtractionResult:
        """Select best candidate with safety rules"""
        if not candidates:
            return CompanyExtractionResult(
                company_name='Unknown',
                confidence=0,
                source='UNKNOWN',
                ats_provider=ats_provider,
                candidates=[]
            )
        
        # Sort by score descending
        candidates.sort(key=lambda x: x.score, reverse=True)
        top_candidate = candidates[0]
        
        # Safety rules
        # Rule 1: If top score < 70, return Unknown
        if top_candidate.score < 70:
            return CompanyExtractionResult(
                company_name='Unknown',
                confidence=top_candidate.score,
                source='UNKNOWN',
                ats_provider=ats_provider,
                candidates=[self._candidate_to_dict(c) for c in candidates]
            )
        
        # Rule 2: If in denylist, force Unknown
        if top_candidate.name.lower() in DENYLIST:
            return CompanyExtractionResult(
                company_name='Unknown',
                confidence=0,
                source='UNKNOWN',
                ats_provider=ats_provider,
                candidates=[self._candidate_to_dict(c) for c in candidates]
            )
        
        # Rule 3: If equals ATS provider name, reject unless no other option
        if top_candidate.name.lower() == ats_provider and len(candidates) > 1:
            # Try next candidate
            for candidate in candidates[1:]:
                if candidate.score >= 70 and candidate.name.lower() != ats_provider:
                    top_candidate = candidate
                    break
            else:
                # No good alternative, return Unknown
                return CompanyExtractionResult(
                    company_name='Unknown',
                    confidence=top_candidate.score,
                    source='UNKNOWN',
                    ats_provider=ats_provider,
                    candidates=[self._candidate_to_dict(c) for c in candidates]
                )
        
        # Normalize company name
        company_name = self._normalize_company(top_candidate.name)
        
        # Apply aliases
        if company_name.lower() in self.company_aliases:
            company_name = self.company_aliases[company_name.lower()]
        
        return CompanyExtractionResult(
            company_name=company_name,
            confidence=top_candidate.score,
            source=top_candidate.source,
            ats_provider=ats_provider,
            candidates=[self._candidate_to_dict(c) for c in candidates]
        )
    
    def _extract_domain(self, email: str) -> Optional[str]:
        """Extract and normalize domain from email"""
        if '@' not in email:
            return None
        
        domain = email.split('@')[1].lower()
        
        # Strip subdomains
        subdomain_prefixes = ['mail.', 'emails.', 'notify.', 'noreply.', 'no-reply.', 'jobs.', 'careers.', 'hiring.', 'talent.']
        for prefix in subdomain_prefixes:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
                break
        
        # Remove common TLDs for matching
        domain_base = domain.split('.')[0]
        
        return domain
    
    def _map_domain_to_company(self, domain: str) -> Optional[str]:
        """Map domain to company name"""
        # Check exact match
        if domain in self.company_domains:
            return self.company_domains[domain]
        
        # Check base domain (without TLD)
        domain_base = domain.split('.')[0]
        if domain_base in self.company_domains:
            return self.company_domains[domain_base]
        
        # Check if domain contains known company
        for known_domain, company in self.company_domains.items():
            if known_domain in domain or domain in known_domain:
                return company
        
        return None
    
    def _normalize_slug(self, slug: str) -> str:
        """Normalize ATS slug to company name"""
        # Convert kebab-case to Title Case
        words = slug.split('-')
        normalized = ' '.join(word.capitalize() for word in words)
        return normalized
    
    def _normalize_company(self, name: str) -> str:
        """Normalize company name"""
        if not name:
            return name
        
        # Trim and collapse spaces
        name = ' '.join(name.split())
        
        # Remove suffix noise
        name = re.sub(r'\s+(Inc|LLC|Ltd|Co\.|Corporation|Corp)$', '', name, flags=re.IGNORECASE)
        
        # Title case but preserve known brand casing
        # For now, simple title case
        words = name.split()
        normalized_words = []
        for word in words:
            if word.isupper() and len(word) > 1:
                normalized_words.append(word)  # Keep acronyms
            else:
                normalized_words.append(word.capitalize())
        
        return ' '.join(normalized_words)
    
    def _candidate_to_dict(self, candidate: CompanyCandidate) -> Dict:
        """Convert CompanyCandidate to dict for JSON serialization"""
        return {
            'name': candidate.name,
            'score': candidate.score,
            'source': candidate.source,
            'evidence': candidate.evidence
        }
    
    def extract_role(self, subject: str, snippet: str) -> Optional[str]:
        """
        Extract job role from subject and snippet
        Returns role string or None
        """
        if not subject and not snippet:
            return None
        
        text = f"{subject} {snippet}".lower()
        
        # Common role patterns
        role_patterns = [
            r'software\s+engineer',
            r'backend\s+engineer',
            r'frontend\s+engineer',
            r'full\s+stack\s+engineer',
            r'devops\s+engineer',
            r'data\s+scientist',
            r'product\s+manager',
            r'product\s+designer',
            r'ui/ux\s+designer',
            r'marketing\s+manager',
            r'sales\s+representative',
            r'account\s+manager',
            r'business\s+analyst',
            r'project\s+manager',
        ]
        
        for pattern in role_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                role = match.group(0).strip()
                # Title case
                words = role.split()
                role = ' '.join(word.capitalize() for word in words)
                return role
        
        # Try to extract from subject patterns like "Software Engineer - Company"
        subject_pattern = r'^([A-Z][a-zA-Z\s]+?)\s*[-–—]\s*'
        match = re.search(subject_pattern, subject)
        if match:
            potential_role = match.group(1).strip()
            # Check if it looks like a role (not a company name)
            if len(potential_role.split()) <= 3 and not any(word in potential_role.lower() for word in ['inc', 'llc', 'corp', 'company']):
                return potential_role
        
        return None
