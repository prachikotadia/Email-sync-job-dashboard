"""
Hugging Face ONNX Classifier for Email Classification

Singleton-style classifier:
- Loads tokenizer + ONNX session once
- Provides classify_one and classify_batch
"""

from __future__ import annotations
import os
import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logging.warning("onnxruntime not available")

try:
    from transformers import AutoTokenizer, AutoConfig
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("transformers not available")

from .mapping import HF_LABEL_TO_STATUS, ALIASES

logger = logging.getLogger(__name__)


class JobEmailClassifier:
    """
    Singleton-style classifier:
    - Loads tokenizer + ONNX session once
    - Provides classify_one and classify_batch
    """

    def __init__(self, model_dir: str, onnx_path: str):
        if not ONNX_AVAILABLE:
            raise ImportError("onnxruntime is required. Install with: pip install onnxruntime")
        
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers is required. Install with: pip install transformers")
        
        self.model_dir = model_dir
        self.onnx_path = onnx_path

        # 1) Load tokenizer (reads tokenizer.json/tokenizer_config.json/config.json)
        # Using local folder ensures consistency.
        # CRITICAL: local_files_only=True to prevent downloading from HF Hub in production
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            use_fast=True,
            local_files_only=True
        )
        logger.info(f"Loaded tokenizer from: {model_dir}")

        # 2) Load ONNX session once
        # CPUExecutionProvider is default; you can also tune intra_op threads.
        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = max(1, os.cpu_count() // 2)
        sess_opts.inter_op_num_threads = 1
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            onnx_path,
            sess_options=sess_opts,
            providers=["CPUExecutionProvider"],
        )
        logger.info(f"Loaded ONNX model from: {onnx_path}")
        logger.info(f"Available providers: {self.session.get_providers()}")

        # 3) Discover output name(s)
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.output_names = [o.name for o in self.session.get_outputs()]

        # Many classifiers output "logits"
        # We'll handle either logits or first output as logits.
        self.logits_name = "logits" if "logits" in self.output_names else self.output_names[0]
        logger.info(f"Using output: {self.logits_name}")

        # 4) Get id2label mapping from config if available
        # Transformers tokenizer loads config.json via AutoTokenizer path; we can also load AutoConfig,
        # but simplest is to hardcode fallback for your known model labels.
        self.id2label = None
        try:
            cfg = AutoConfig.from_pretrained(model_dir, local_files_only=True)
            self.id2label = getattr(cfg, "id2label", None)
            if self.id2label:
                # Convert string keys to int if needed
                self.id2label = {int(k): v for k, v in self.id2label.items()}
                logger.info(f"Loaded id2label mapping: {self.id2label}")
        except Exception as e:
            logger.debug(f"Failed to load id2label from config: {e}")
            self.id2label = None

    def _build_text(self, subject: str, snippet: str, from_domain: str, thread_summary: str) -> str:
        # Keep this template stable; it improves model consistency.
        return (
            f"SUBJECT: {subject or ''}\n"
            f"SNIPPET: {snippet or ''}\n"
            f"SENDER_DOMAIN: {from_domain or ''}\n"
            f"THREAD_SUMMARY: {thread_summary or ''}"
        ).strip()

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        x = x - np.max(x, axis=-1, keepdims=True)
        e = np.exp(x)
        return e / np.sum(e, axis=-1, keepdims=True)

    def _postprocess(self, probs: np.ndarray) -> Tuple[str, float]:
        idx = int(np.argmax(probs))
        conf = float(probs[idx])

        # Map index -> label
        if self.id2label and idx in self.id2label:
            label = self.id2label[idx]
        else:
            # Fallback: assume standard 5-class order is in model config,
            # but if missing, you MUST confirm order once by printing outputs.
            # Safer fallback is to read config.json via AutoConfig above.
            # Use mapping order as fallback
            labels = list(HF_LABEL_TO_STATUS.keys())
            if idx < len(labels):
                label = labels[idx]
            else:
                label = str(idx)

        # normalize label (handle aliases)
        label_upper = label.upper()
        label_norm = ALIASES.get(label_upper, label.lower())
        return label_norm, conf

    def classify_one(
        self,
        subject: str = "",
        snippet: str = "",
        from_domain: str = "",
        thread_summary: str = ""
    ) -> Dict[str, Any]:
        """
        Classify a single email.
        
        Args:
            subject: Email subject
            snippet: Email snippet
            from_domain: Sender domain
            thread_summary: Thread summary
        
        Returns:
            Dictionary with label, status, confidence, and reason
        """
        text = self._build_text(subject, snippet, from_domain, thread_summary)

        # Tokenize -> numpy arrays
        enc = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=256,          # safe default; you can tune later
            return_tensors="np",
        )

        feeds = {}
        # Common transformer inputs:
        # input_ids, attention_mask, token_type_ids (maybe)
        for k, v in enc.items():
            if k in self.input_names:
                feeds[k] = v.astype(np.int64)

        outputs = self.session.run([self.logits_name], feeds)
        logits = outputs[0]                      # shape: (1, num_labels)
        probs = self._softmax(logits)[0]         # shape: (num_labels,)

        label, confidence = self._postprocess(probs)
        status = HF_LABEL_TO_STATUS.get(label, "ACTIVE")  # safe fallback

        return {
            "label": label,
            "status": status,
            "confidence": confidence,
            "reason": f"HF ONNX model predicted {label} ({confidence:.2f})",
        }

    def classify_batch(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Classify a batch of emails.
        
        Args:
            items: List of dictionaries with subject, snippet, from_domain, thread_summary
        
        Returns:
            List of classification results
        """
        # Batch tokenization
        texts = [
            self._build_text(
                it.get("subject", ""),
                it.get("snippet", ""),
                it.get("from_domain", ""),
                it.get("thread_summary", ""),
            )
            for it in items
        ]

        enc = self.tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=256,
            return_tensors="np",
        )

        feeds = {}
        for k, v in enc.items():
            if k in self.input_names:
                feeds[k] = v.astype(np.int64)

        outputs = self.session.run([self.logits_name], feeds)
        logits = outputs[0]                  # (B, num_labels)
        probs = self._softmax(logits)        # (B, num_labels)

        results = []
        for i in range(probs.shape[0]):
            label, confidence = self._postprocess(probs[i])
            status = HF_LABEL_TO_STATUS.get(label, "ACTIVE")
            results.append({
                "label": label,
                "status": status,
                "confidence": float(confidence),
                "reason": f"HF ONNX model predicted {label} ({confidence:.2f})",
            })
        return results


# ------- Singleton holder -------
_classifier: Optional[JobEmailClassifier] = None

def init_classifier(model_dir: str, onnx_path: str) -> None:
    """
    Initialize the singleton classifier.
    
    Call this once at application startup.
    
    Args:
        model_dir: Directory containing tokenizer.json/config.json/etc
        onnx_path: Path to ONNX model file
    """
    global _classifier
    if _classifier is not None:
        logger.warning("Classifier already initialized. Re-initializing...")
    _classifier = JobEmailClassifier(model_dir=model_dir, onnx_path=onnx_path)
    logger.info("Classifier initialized successfully")

def get_classifier() -> JobEmailClassifier:
    """
    Get the singleton classifier instance.
    
    Returns:
        JobEmailClassifier instance
    
    Raises:
        RuntimeError: If classifier not initialized
    """
    if _classifier is None:
        raise RuntimeError("Classifier not initialized. Call init_classifier() at startup.")
    return _classifier
