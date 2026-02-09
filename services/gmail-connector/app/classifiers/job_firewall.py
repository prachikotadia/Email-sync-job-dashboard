"""
Job Email Firewall - Deny-first, allow-only. Blocks non-job emails BEFORE any classifier.
Deterministic and explainable: stores exact matched rule IDs + reason.
"""
import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
logger = logging.getLogger(__name__)

_config: Optional[Dict] = None


def _load_config() -> Dict:
    global _config
    if _config is not None:
        return _config
    paths = [
        Path("config/job_firewall.yaml"),
        Path("../config/job_firewall.yaml"),
        Path("../../config/job_firewall.yaml"),
        Path("/app/config/job_firewall.yaml"),
    ]
    for p in paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    root = yaml.safe_load(f)
                _config = root.get("job_firewall", {})
                logger.info(f"Loaded job_firewall from {p}")
                return _config
            except Exception as e:
                logger.error(f"Failed to load job_firewall from {p}: {e}")
    _config = {
        "deny": {"domains": [], "keywords": {}},
        "allow": {"ats_domains": [], "strong_job_phrases": []},
        "gmail_deny_categories": ["CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"],
        "job_alert_domains": ["indeed.com", "builtin.com"],
        "job_alert_subject_phrases": ["job matches", "jobs just dropped", "recommendations"],
    }
    return _config


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _rule(id_: str, type_: str, value: str) -> Dict[str, str]:
    return {"id": id_, "type": type_, "value": value}


def _has_strong_job_signal(
    text: str,
    from_domain: str,
    ats_domains: List[str],
    strong_phrases: List[str],
) -> bool:
    """True if ATS domain or strong job phrase present."""
    if not text:
        text = ""
    text_n = _normalize(text)
    domain = (from_domain or "").lower()
    for ats in ats_domains:
        if domain == ats or domain.endswith("." + ats):
            return True
    for phrase in strong_phrases:
        if _normalize(phrase) in text_n:
            return True
    return False


def firewall(
    subject: str = "",
    snippet: str = "",
    from_email: str = "",
    from_domain: str = "",
    headers: Optional[Dict[str, str]] = None,
    gmail_label_ids: Optional[List[str]] = None,
    gmail_category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic job email firewall. Deny-first, allow-only.
    Returns:
      allow: bool
      decision: "ALLOW" | "DENY"
      category: "NON_JOB_AUTH"|"NON_JOB_PROMO"|"NON_JOB_ALERT"|"NON_JOB_SUPPORT"|"NON_JOB_BILLING"|"NON_JOB_DEVOPS"|"JOB"
      matched_rules: [ {id, type, value}, ... ]
      reason: str
    """
    cfg = _load_config()
    subject = subject or ""
    snippet = snippet or ""
    from_email = from_email or ""
    if not from_domain and "@" in from_email:
        from_domain = from_email.split("@", 1)[1].lower()
    from_domain = (from_domain or "").lower()
    headers = headers or {}
    gmail_label_ids = gmail_label_ids or []
    gmail_category = (gmail_category or "").strip()

    # Combined text for keyword matching (subject + snippet + header values)
    header_text = " ".join(str(v) for v in headers.values()) if headers else ""
    combined = _normalize(f"{subject} {snippet} {header_text}")

    matched_rules: List[Dict[str, str]] = []
    category = "UNKNOWN"

    # ---- 1) Gmail category PROMOTIONS / SOCIAL → DENY unless strong job ----
    gmail_deny = [x.upper() for x in (cfg.get("gmail_deny_categories", []) or [])]
    labels_upper = [str(s).upper() for s in gmail_label_ids]
    in_deny_category = any(
        label in gmail_deny for label in labels_upper
    ) or (gmail_category and str(gmail_category).upper() in gmail_deny)
    if in_deny_category:
        ats = cfg.get("allow", {}).get("ats_domains", [])
        strong = cfg.get("allow", {}).get("strong_job_phrases", [])
        if _has_strong_job_signal(combined, from_domain, ats, strong):
            matched_rules.append(_rule("gmail_category_override", "allow", "strong_job_signal"))
            # Fall through to allow check later
        else:
            matched_rules.append(_rule("gmail_category_deny", "deny", "CATEGORY_PROMOTIONS_OR_SOCIAL"))
            return {
                "allow": False,
                "decision": "DENY",
                "category": "NON_JOB_PROMO",
                "matched_rules": matched_rules,
                "reason": "Gmail category promotions/social; no strong job signal",
            }

    # ---- 2) DENY domain (exact or suffix) ----
    deny_domains = cfg.get("deny", {}).get("domains", [])
    for entry in deny_domains:
        if isinstance(entry, dict):
            value = (entry.get("value") or "").lower()
            cat = entry.get("category", "UNKNOWN")
        else:
            value = (entry or "").lower()
            cat = "UNKNOWN"
        if not value:
            continue
        if from_domain == value or from_domain.endswith("." + value):
            matched_rules.append(_rule(f"domain_deny:{value}", "deny", value))
            return {
                "allow": False,
                "decision": "DENY",
                "category": cat,
                "matched_rules": matched_rules,
                "reason": f"Deny domain: {value}",
            }

    # ---- 3) DENY keywords (subject OR snippet OR headers) ----
    keywords_cfg = cfg.get("deny", {}).get("keywords", {})
    if isinstance(keywords_cfg, dict):
        for key, block in keywords_cfg.items():
            if not isinstance(block, dict):
                continue
            cat = block.get("category", "UNKNOWN")
            phrases = block.get("phrases", [])
            if isinstance(phrases, str):
                phrases = [phrases]
            for phrase in phrases:
                pn = _normalize(phrase)
                if pn and pn in combined:
                    matched_rules.append(_rule(f"keyword_deny:{key}:{phrase}", "deny", phrase))
                    return {
                        "allow": False,
                        "decision": "DENY",
                        "category": cat,
                        "matched_rules": matched_rules,
                        "reason": f"Deny keyword: {phrase}",
                    }

    # ---- 4) Job-board alert: indeed/builtin or subject phrases → NON_JOB_ALERT ----
    job_alert_domains = [d.lower() for d in cfg.get("job_alert_domains", [])]
    job_alert_phrases = [_normalize(p) for p in cfg.get("job_alert_subject_phrases", [])]
    if from_domain in job_alert_domains or any(from_domain.endswith("." + d) for d in job_alert_domains):
        matched_rules.append(_rule("job_alert_domain", "deny", from_domain))
        return {
            "allow": False,
            "decision": "DENY",
            "category": "NON_JOB_ALERT",
            "matched_rules": matched_rules,
            "reason": f"Job-board alert domain: {from_domain}",
        }
    for p in job_alert_phrases:
        if p and p in combined:
            matched_rules.append(_rule("job_alert_phrase", "deny", p))
            return {
                "allow": False,
                "decision": "DENY",
                "category": "NON_JOB_ALERT",
                "matched_rules": matched_rules,
                "reason": f"Job-board alert phrase: {p}",
            }

    # ---- 5) Only ALLOW if at least one strong job signal ----
    ats_domains = cfg.get("allow", {}).get("ats_domains", [])
    strong_phrases = cfg.get("allow", {}).get("strong_job_phrases", [])
    if _has_strong_job_signal(combined, from_domain, ats_domains, strong_phrases):
        # Attach which rule allowed (first match)
        for ats in ats_domains:
            if from_domain == ats or from_domain.endswith("." + ats):
                matched_rules.append(_rule(f"allow_ats:{ats}", "allow", ats))
                return {
                    "allow": True,
                    "decision": "ALLOW",
                    "category": "JOB",
                    "matched_rules": matched_rules,
                    "reason": f"ATS domain: {ats}",
                }
        for phrase in strong_phrases:
            if _normalize(phrase) in combined:
                matched_rules.append(_rule("allow_phrase", "allow", phrase))
                return {
                    "allow": True,
                    "decision": "ALLOW",
                    "category": "JOB",
                    "matched_rules": matched_rules,
                    "reason": f"Strong job phrase: {phrase}",
                }

    # Default: DENY (no allow signal)
    return {
        "allow": False,
        "decision": "DENY",
        "category": "UNKNOWN",
        "matched_rules": matched_rules,
        "reason": "No strong job signal; blocked by default",
    }


def firewall_for_sync(subject: str, snippet: str, from_email: str, from_domain: str, headers: Optional[Dict], label_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convenience wrapper for sync pipeline. Returns same shape as firewall() plus
    allow_job_pipeline (bool) and matched_rules as list of dicts (for DB JSON).
    """
    result = firewall(
        subject=subject,
        snippet=snippet,
        from_email=from_email,
        from_domain=from_domain,
        headers=headers,
        gmail_label_ids=label_ids,
        gmail_category=None,
    )
    out = dict(result)
    out["allow_job_pipeline"] = result.get("allow", False)
    out["matched_rules"] = result.get("matched_rules", [])
    return out
