"""
RejectGate: Fast rejection detection using TF-IDF + Logistic Regression.

This service loads a pre-trained model at startup and provides fast inference
to detect rejection emails before running the full classification pipeline.

Priority: If RejectGate says REJECTED, set status=REJECTED and stop processing.
"""
import json
import joblib
import re
import os
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_reject_gate = None
_thr = 0.85

PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")

def _norm(s: str) -> str:
    """Normalize text: lowercase, collapse whitespace, replace proper nouns with <TOKEN>."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = PROPER_NOUN_RE.sub("<TOKEN>", s)
    return s.lower()

def init_reject_gate():
    """
    Initialize RejectGate model at startup.
    Loads model and metadata from models/reject_gate/ directory.
    
    Raises:
        RuntimeError: If model file not found
    """
    global _reject_gate, _thr
    
    # Try multiple possible paths (workspace root or service root)
    base_paths = [
        Path(__file__).parent.parent.parent.parent,  # From services/gmail-connector/app/services/ -> workspace root
        Path(__file__).parent.parent.parent.parent.parent,  # Alternative path
        Path("."),  # Current directory
    ]
    
    model_path = None
    meta_path = None
    
    for base in base_paths:
        candidate_model = base / "models" / "reject_gate" / "reject_gate.joblib"
        candidate_meta = base / "models" / "reject_gate" / "reject_gate.meta.json"
        if candidate_model.exists():
            model_path = candidate_model
            meta_path = candidate_meta
            break
    
    if model_path is None or not model_path.exists():
        # Try absolute path from environment or default
        default_model = Path("models/reject_gate/reject_gate.joblib")
        if default_model.exists():
            model_path = default_model
            meta_path = Path("models/reject_gate/reject_gate.meta.json")
        else:
            raise RuntimeError(
                f"RejectGate model not found. Expected at: {model_path or 'models/reject_gate/reject_gate.joblib'}. "
                "Please run ml/train_reject_gate.py first."
            )
    
    logger.info(f"Loading RejectGate model from: {model_path}")
    _reject_gate = joblib.load(model_path)

    if meta_path and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        _thr = float(meta.get("recommended_threshold", 0.85))
        logger.info(f"RejectGate threshold: {_thr}")
    else:
        logger.warning(f"RejectGate metadata not found at {meta_path}, using default threshold: {_thr}")

def predict_reject_gate(subject: str = "", snippet: str = "", from_domain: str = "") -> Dict:
    """
    Predict if email is a rejection using RejectGate.
    
    Works with both old and improved model versions:
    - Old: Simple TF-IDF + Logistic Regression pipeline
    - Improved: FeatureUnion with TF-IDF + rejection keyword features
    
    Args:
        subject: Email subject line
        snippet: Email snippet/preview
        from_domain: Sender domain
    
    Returns:
        Dict with:
            - is_rejected: bool (True if p_rejected >= threshold)
            - p_rejected: float (probability of rejection, 0-1)
            - threshold: float (threshold used)
            - label: str ("REJECTED" or "NOT_REJECTED")
            - reason: str (human-readable explanation)
    
    Raises:
        RuntimeError: If RejectGate not initialized
    """
    if _reject_gate is None:
        raise RuntimeError("RejectGate not initialized. Call init_reject_gate() at startup.")

    # Prepare text input (same format as training)
    text = f"subject: {_norm(subject)} | snippet: {_norm(snippet)} | domain: {_norm(from_domain)}"
    
    # Predict probability (works with both old and improved models)
    # The improved model uses FeatureUnion which accepts the same text input
    try:
        p_rejected = float(_reject_gate.predict_proba([text])[0][1])  # class 1 = REJECTED
    except Exception as e:
        logger.error(f"RejectGate prediction error: {e}")
        # Fallback: return NOT_REJECTED if prediction fails
        p_rejected = 0.0
    
    is_rejected = p_rejected >= _thr

    return {
        "is_rejected": is_rejected,
        "p_rejected": p_rejected,
        "threshold": _thr,
        "label": "REJECTED" if is_rejected else "NOT_REJECTED",
        "reason": f"RejectGate p={p_rejected:.3f} (thr={_thr:.2f})",
    }

def is_initialized() -> bool:
    """Check if RejectGate is initialized."""
    return _reject_gate is not None
