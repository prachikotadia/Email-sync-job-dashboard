"""
Classification Mapping

Maps Hugging Face model labels to classification statuses.
"""

from enum import Enum
from typing import Dict, Optional


class ClassificationStatus(str, Enum):
    """Email classification statuses."""
    ACTIVE = "ACTIVE"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    OFFER = "OFFER"
    GHOSTED = "GHOSTED"
    WITHDRAWN = "WITHDRAWN"
    IGNORE = "IGNORE"


# Hugging Face label to status mapping
HF_LABEL_TO_STATUS = {
    "confirmation": "ACTIVE",
    "interview": "INTERVIEW",
    "rejection": "REJECTED",
    "offer": "OFFER",
    "not_job": "IGNORE",
}

# Optional: accept aliases (sometimes models output uppercase or different keys)
ALIASES = {
    "CONFIRMATION": "confirmation",
    "INTERVIEW": "interview",
    "REJECTION": "rejection",
    "OFFER": "offer",
    "NOT_JOB": "not_job",
}


class ClassificationMapping:
    """
    Maps Hugging Face model labels to classification statuses.
    
    Supports both label strings and numeric indices.
    """
    
    def __init__(
        self,
        label_to_status: Optional[Dict[str, str]] = None,
        aliases: Optional[Dict[str, str]] = None,
        idx_to_status: Optional[Dict[int, str]] = None
    ):
        """
        Initialize mapping.
        
        Args:
            label_to_status: Custom label to status mapping (default: HF_LABEL_TO_STATUS)
            aliases: Custom aliases mapping (default: ALIASES)
            idx_to_status: Custom index to status mapping (optional, for numeric outputs)
        """
        # Use provided mappings or defaults
        self.label_to_status_map = label_to_status or HF_LABEL_TO_STATUS.copy()
        self.aliases = aliases or ALIASES.copy()
        
        # Index-based mapping (for models that output numeric indices)
        if idx_to_status:
            self.idx_to_status_map = idx_to_status
        else:
            # Default index mapping based on label order
            labels = list(self.label_to_status_map.keys())
            self.idx_to_status_map = {
                idx: self.label_to_status_map[label]
                for idx, label in enumerate(labels)
            }
        
        # Reverse mappings
        self.status_to_label_map = {v: k for k, v in self.label_to_status_map.items()}
        self.status_to_idx_map = {v: k for k, v in self.idx_to_status_map.items()}
    
    def normalize_label(self, label: str) -> str:
        """
        Normalize label using aliases.
        
        Args:
            label: Raw label from model
        
        Returns:
            Normalized label
        """
        # Check aliases first
        normalized = self.aliases.get(label.upper(), label.lower())
        return normalized
    
    def label_to_status(self, label: str) -> str:
        """
        Convert Hugging Face label to status.
        
        Args:
            label: Model output label (e.g., "confirmation", "interview")
        
        Returns:
            Classification status string (e.g., "ACTIVE", "INTERVIEW")
        """
        # Normalize label (handle aliases)
        normalized_label = self.normalize_label(label)
        
        # Map to status
        status = self.label_to_status_map.get(normalized_label, ClassificationStatus.ACTIVE.value)
        return status
    
    def idx_to_status(self, idx: int) -> str:
        """
        Convert model output index to status.
        
        Args:
            idx: Model output index
        
        Returns:
            Classification status string
        """
        return self.idx_to_status_map.get(idx, ClassificationStatus.ACTIVE.value)
    
    def status_to_label(self, status: str) -> str:
        """
        Convert status to Hugging Face label.
        
        Args:
            status: Classification status string
        
        Returns:
            Hugging Face label
        """
        return self.status_to_label_map.get(status.upper(), "confirmation")
    
    def status_to_idx(self, status: str) -> int:
        """
        Convert status to model output index.
        
        Args:
            status: Classification status string
        
        Returns:
            Model output index
        """
        return self.status_to_idx_map.get(status.upper(), 0)
