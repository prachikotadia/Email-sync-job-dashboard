"""
ATS-aware Company Resolver. Never use ATS infra tokens (us, eu, na) or ATS domain as company.
Returns: company_name, company_source, company_confidence, company_debug (candidates, picked_rule, rejected).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

# ATS domains — domain-derived company forbidden; use fallback label only
ATS_DOMAINS = {
    "greenhouse-mail.io",
    "greenhouse.io",
    "lever.co",
    "workday.com",
    "myworkday.com",
    "myworkdayjobs.com",
    "icims.com",
    "smartrecruiters.com",
    "taleo.net",
    "successfactors.com",
    "ashbyhq.com",
    "jobvite.com",
    "brassring.com",
    "bamboohr.com",
    "workable.com",
}

# Never treat as company (infra tokens + generic)
INFRA_AND_STOPLIST = {
    "us", "eu", "na", "apac", "prod", "staging", "mail", "noreply", "no-reply",
    "notifications", "team", "careers", "recruiting", "talent", "hiring",
    "greenhouse", "workday", "applications", "jobs", "board", "apply", "embed",
}

# Suffixes to strip from candidate
SUFFIXES_STRIP = [
    "careers", "recruiting", "talent", "talent acquisition", "hiring team",
    "team", "inc", "inc.", "llc", "ltd", "ltd.", "corp", "corporation", "co", "co.",
    "pvt", "limited",
]

GREENHOUSE_ATS_FALLBACK = "Greenhouse (ATS)"
WORKDAY_ATS_FALLBACK = "Workday (ATS)"
MAX_COMPANY_LEN = 50


def _strip_punctuation_and_emoji(raw: str) -> str:
    if not raw:
        return ""
    # Remove common punctuation and emoji ranges
    s = re.sub(r"[\u2014\u2013\-.,!?;:\"\'()\[\]{}]+", " ", raw)
    s = re.sub(r"[\U0001F300-\U0001F9FF]", "", s)  # emoji
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_candidate(raw: str, max_len: int = MAX_COMPANY_LEN) -> Optional[str]:
    """Strip punctuation/emoji, remove suffixes, title case, cap length. Returns None if rejected."""
    if not raw or not raw.strip():
        return None
    s = _strip_punctuation_and_emoji(raw)
    s = s[:max_len].strip()
    s_lower = s.lower()
    for suffix in SUFFIXES_STRIP:
        s_lower = re.sub(rf"\s+{re.escape(suffix)}\s*$", "", s_lower, flags=re.IGNORECASE)
        s_lower = re.sub(rf"^\s*{re.escape(suffix)}\s+", "", s_lower, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s_lower).strip()
    if len(s) < 2:
        return None
    # Title case
    words = s.split()
    out = []
    for w in words:
        if w in ("and", "of", "the", "at", "in", "on", "for", "with"):
            out.append(w)
        else:
            out.append(w.capitalize())
    result = " ".join(out)
    if result.lower() in INFRA_AND_STOPLIST:
        return None
    return result


def _slug_to_title(slug: str) -> str:
    """my-company -> My Company, faire -> Faire"""
    if not slug:
        return ""
    return " ".join(p.capitalize() for p in slug.replace("_", " ").split("-"))


def _is_ats_domain(domain: str) -> bool:
    if not domain:
        return False
    d = domain.lower()
    return any(ats in d for ats in ATS_DOMAINS)


def _get_ats_fallback_label(domain: str) -> str:
    if "greenhouse" in (domain or "").lower():
        return GREENHOUSE_ATS_FALLBACK
    if "workday" in (domain or "").lower():
        return WORKDAY_ATS_FALLBACK
    return "Unknown Company"


def _collect_subject_candidates(subject: str) -> List[Tuple[str, float, str]]:
    """Returns [(company, score, picked_rule), ...]"""
    out = []
    if not subject or not subject.strip():
        return out
    sub = subject.strip()
    patterns = [
        (r"thank\s+you\s+for\s+applying\s+to\s+(.+?)[!.\-]?\s*$", 1.0, "subject:thank_you_for_applying_to"),
        (r"update\s+on\s+your\s+application\s*[-—]\s*(.+?)(?:\s*$|\s*[-–—])", 1.0, "subject:update_on_application"),
        (r"application\s+(?:received|confirmation)\s*[-—]\s*(.+?)(?:\s*$|\s*[-–—])", 1.0, "subject:application_received"),
        (r"your\s+application\s+to\s+(.+?)(?:\s*$|[!.\-])", 1.0, "subject:your_application_to"),
        (r"application\s+update\s*[-—]\s*(.+?)(?:\s*$|\s*[-–—])", 1.0, "subject:application_update"),
    ]
    for pattern, score, rule in patterns:
        m = re.search(pattern, sub, re.IGNORECASE)
        if m:
            c = _normalize_candidate(m.group(1))
            if c:
                out.append((c, score, rule))
    return out


def _collect_signature_candidates(text: str) -> List[Tuple[str, float, str]]:
    """From body_text or snippet: The {X} Team, {X} Recruiting, {X} Talent Acquisition."""
    out = []
    if not text or not text.strip():
        return out
    combined = " " + (text.strip()) + " "
    patterns = [
        (r"\bthe\s+(.+?)\s+team\b", 0.9, "signature:the_x_team"),
        (r"\b(.+?)\s+recruiting\b", 0.9, "signature:x_recruiting"),
        (r"\b(.+?)\s+talent\s+acquisition\b", 0.9, "signature:x_talent_acquisition"),
        (r"\bthanks,?\s*(.+?)(?:\s*$|\n|\.)", 0.85, "signature:thanks_x"),
    ]
    for pattern, score, rule in patterns:
        for m in re.finditer(pattern, combined, re.IGNORECASE):
            c = _normalize_candidate(m.group(1))
            if c and c.lower() not in INFRA_AND_STOPLIST:
                out.append((c, score, rule))
    return out


def _collect_link_candidates(urls: List[str]) -> List[Tuple[str, float, str]]:
    """Greenhouse, Lever, Workday URL parsing. Score 0.85."""
    out = []
    bad = {"jobs", "careers", "board", "job", "apply", "embed"} | INFRA_AND_STOPLIST
    for url in (urls or [])[:5]:
        url_lower = url.lower()
        if "boards.greenhouse.io" in url_lower or "job-boards.greenhouse.io" in url_lower or "/" in url_lower and "greenhouse.io" in url_lower:
            m = re.search(r"greenhouse\.io/([a-zA-Z0-9_-]+)", url_lower, re.IGNORECASE)
            if m:
                slug = m.group(1).lower()
                if slug not in bad:
                    name = _slug_to_title(slug)
                    if name:
                        out.append((name, 0.85, "link:greenhouse_slug"))
        if "lever.co" in url_lower:
            m = re.search(r"lever\.co/([a-zA-Z0-9_-]+)", url_lower, re.IGNORECASE)
            if m:
                slug = m.group(1).lower()
                if slug not in bad:
                    name = _slug_to_title(slug)
                    if name:
                        out.append((name, 0.85, "link:lever_slug"))
        if "workday.com" in url_lower or "myworkdayjobs.com" in url_lower:
            host_m = re.search(r"https?://([^/]+)", url_lower)
            if host_m:
                host = host_m.group(1).lower()
                parts = host.split(".")
                skip = {"www", "wd", "wd1", "wd2", "wd3", "my", "jobs", "workday", "com", "myworkdayjobs"} | INFRA_AND_STOPLIST
                tenant = next((p for p in parts if p not in skip and len(p) > 1), None)
                if tenant:
                    name = _slug_to_title(tenant)
                    if name:
                        out.append((name, 0.85, "link:workday_tenant"))
        if "icims.com" in url_lower:
            m = re.search(r"icims\.com/jobs/([a-zA-Z0-9_-]+)", url_lower, re.IGNORECASE)
            if m:
                slug = m.group(1).lower()
                if slug not in bad:
                    out.append((_slug_to_title(slug), 0.85, "link:icims"))
        if "smartrecruiters.com" in url_lower:
            m = re.search(r"smartrecruiters\.com/([a-zA-Z0-9_-]+)", url_lower, re.IGNORECASE)
            if m:
                slug = m.group(1).lower()
                if slug not in bad:
                    out.append((_slug_to_title(slug), 0.85, "link:smartrecruiters"))
    return out


def _collect_from_name_candidates(from_name: str) -> List[Tuple[str, float, str]]:
    """Faire Recruiting -> Faire. Reject Greenhouse, Workday (generic). Score 0.6."""
    out = []
    if not from_name or not from_name.strip():
        return out
    name = from_name.strip()
    if name.lower() in ("greenhouse", "workday"):
        return out
    for suffix in ["Recruiting", "Careers", "Talent Acquisition", "Talent", "HR", "Hiring", "Jobs", "Team"]:
        if name.lower().endswith(" " + suffix.lower()):
            candidate = name[: -(len(suffix) + 1)].strip()
            c = _normalize_candidate(candidate)
            if c and c.lower() not in INFRA_AND_STOPLIST:
                out.append((c, 0.6, "from_name:suffix_strip"))
            break
    else:
        c = _normalize_candidate(name)
        if c and c.lower() not in INFRA_AND_STOPLIST:
            out.append((c, 0.6, "from_name"))
    return out


def _domain_fallback_candidate(from_email: str, from_domain: str) -> Optional[Tuple[str, float, str]]:
    """Only for non-ATS. Root domain -> Company. Score 0.3."""
    if not from_email or "@" not in from_email:
        return None
    domain = from_email.split("@")[1].lower()
    ignore = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "aol.com", "mail.com"}
    if domain in ignore or _is_ats_domain(domain):
        return None
    parts = [p for p in domain.split(".") if p]
    generic = {"mail", "email", "www", "web", "noreply", "hr", "careers", "jobs"} | INFRA_AND_STOPLIST
    for p in parts:
        if p not in generic and len(p) > 1:
            name = p.capitalize()
            if name.lower() not in INFRA_AND_STOPLIST:
                return (name, 0.3, "domain_fallback")
    return None


def resolve_company(
    subject: str = "",
    snippet: str = "",
    from_name: str = "",
    from_email: str = "",
    from_domain: str = "",
    body_text: Optional[str] = None,
    urls: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
    links: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    ATS-aware company resolution. Never use us/eu/na or ATS domain as company.
    body_text and urls preferred; falls back to snippet and links if not provided.

    Returns:
      company_name: str
      company_source: subject | signature | link | from_name | domain_fallback
      company_confidence: 0-1
      company_debug: { candidates: [...], picked_rule: str, rejected: [...] }
    """
    subject = (subject or "").strip()
    snippet = (snippet or "").strip()
    from_name = (from_name or "").strip()
    from_email = (from_email or "").strip()
    from_domain = (from_domain or "").strip().lower()
    if not from_domain and "@" in from_email:
        from_domain = from_email.split("@")[1].lower()
    body_text = (body_text or "").strip()
    urls = urls or links or []
    if not urls and (snippet or subject or body_text):
        urls = re.findall(r"https?://[^\s<>\"']+", (snippet or "") + " " + (body_text or "") + " " + (subject or ""), re.IGNORECASE)
    urls = urls[:5]

    candidates: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    combined_text = (snippet + " " + body_text).strip() or snippet

    # 1) Subject (1.0)
    for company, score, rule in _collect_subject_candidates(subject):
        candidates.append({"value": company, "source": "subject", "score": score, "rule": rule})
    # 2) Signature from body_text + snippet (0.9)
    for company, score, rule in _collect_signature_candidates(combined_text):
        candidates.append({"value": company, "source": "signature", "score": score, "rule": rule})
    # 3) Links (0.85)
    for company, score, rule in _collect_link_candidates(urls):
        candidates.append({"value": company, "source": "link", "score": score, "rule": rule})
    # 4) From name (0.6)
    for company, score, rule in _collect_from_name_candidates(from_name):
        candidates.append({"value": company, "source": "from_name", "score": score, "rule": rule})
    # 5) Domain fallback only if non-ATS (0.3)
    if not _is_ats_domain(from_domain):
        dom = _domain_fallback_candidate(from_email, from_domain)
        if dom:
            company, score, rule = dom
            candidates.append({"value": company, "source": "domain_fallback", "score": score, "rule": rule})

    # Reject infra/generic from any raw extraction (track for debug)
    def is_rejected(value: str) -> bool:
        v = (value or "").strip().lower()
        if len(v) < 2:
            return True
        if v in INFRA_AND_STOPLIST:
            return True
        return False

    # Dedupe by value (keep highest score), then sort by score desc
    by_value: Dict[str, Dict] = {}
    for c in candidates:
        val = c["value"]
        if is_rejected(val):
            rejected.append({"value": val, "reason": "infra_token" if val in INFRA_AND_STOPLIST else "rejected"})
            continue
        if val not in by_value or c["score"] > by_value[val]["score"]:
            by_value[val] = c
    candidates = list(by_value.values())
    candidates.sort(key=lambda x: (-x["score"], x["value"]))

    # Pick best
    if candidates:
        best = candidates[0]
        company_name = best["value"]
        source = best["source"]
        confidence = best["score"]
        picked_rule = best["rule"]
    else:
        # ATS domain: fallback label only (never Us/Eu)
        if _is_ats_domain(from_domain):
            company_name = _get_ats_fallback_label(from_domain)
            source = "domain_fallback"
            confidence = 0.3
            picked_rule = "ats_fallback_label"
            rejected.append({"value": from_domain.split(".")[0] if "." in from_domain else from_domain, "reason": "infra_token"})
        else:
            company_name = "Unknown Company"
            source = "domain_fallback"
            confidence = 0.1
            picked_rule = "none"

    debug_candidates = [{"value": c["value"], "source": c["source"], "score": c["score"]} for c in candidates[:10]]
    debug = {
        "candidates": debug_candidates,
        "picked_rule": picked_rule,
        "rejected": rejected[:20],
    }
    return {
        "company_name": company_name,
        "company_source": source,
        "company_confidence": confidence,
        "company_debug": debug,
    }


def extract_links_from_text(text: str) -> List[str]:
    """Extract URLs from body/snippet (first 5 for resolver)."""
    if not text:
        return []
    urls = re.findall(r"https?://[^\s<>\"']+", text, re.IGNORECASE)
    return list(urls)[:5]
