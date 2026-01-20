"""
Classifier service module for ONNX-based email classification.
"""

from app.services.classifier.hf_onnx_classifier import (
    JobEmailClassifier,
    init_classifier,
    get_classifier
)
from app.services.classifier.mapping import ClassificationMapping, HF_LABEL_TO_STATUS, ALIASES
from app.services.classifier.schemas import EmailForClassification, ClassificationResult

__all__ = [
    "JobEmailClassifier",
    "init_classifier",
    "get_classifier",
    "ClassificationMapping",
    "HF_LABEL_TO_STATUS",
    "ALIASES",
    "EmailForClassification",
    "ClassificationResult"
]
