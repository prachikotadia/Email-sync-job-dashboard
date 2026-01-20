"""
ONNX Runtime + Hugging Face Tokenizers for LLM Inference

This module provides ONNX-based inference for the Local LLM Semantic Classifier (Layer 7).

Usage:
    from app.onnx_llm_inference import ONNXLLMInference
    
    inference = ONNXLLMInference(model_path="path/to/model.onnx", tokenizer_name="bert-base-uncased")
    result = inference.classify(prompt)
"""

import logging
import numpy as np
from typing import Dict, Optional, List
import os
import json
import re

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logging.warning("onnxruntime not available. Install with: pip install onnxruntime")

try:
    from transformers import AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("transformers not available. Install with: pip install transformers")

logger = logging.getLogger(__name__)


class ONNXLLMInference:
    """
    ONNX Runtime inference for email classification.
    
    Uses Hugging Face tokenizers for text preprocessing and ONNX Runtime for fast inference.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        tokenizer_name: Optional[str] = None,
        provider: str = "CPUExecutionProvider"
    ):
        """
        Initialize ONNX inference engine.
        
        Args:
            model_path: Path to ONNX model file (.onnx)
            tokenizer_name: Hugging Face tokenizer name (e.g., "bert-base-uncased")
            provider: ONNX Runtime execution provider (CPUExecutionProvider, CUDAExecutionProvider, etc.)
        """
        if not ONNX_AVAILABLE:
            raise ImportError("onnxruntime is required. Install with: pip install onnxruntime")
        
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers is required. Install with: pip install transformers")
        
        self.model_path = model_path or os.getenv("ONNX_MODEL_PATH")
        self.tokenizer_name = tokenizer_name or os.getenv("ONNX_TOKENIZER_NAME", "bert-base-uncased")
        self.provider = provider
        
        # Initialize tokenizer
        if self.tokenizer_name:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name)
                logger.info(f"Loaded tokenizer: {self.tokenizer_name}")
            except Exception as e:
                logger.error(f"Failed to load tokenizer {self.tokenizer_name}: {e}")
                self.tokenizer = None
        else:
            self.tokenizer = None
        
        # Initialize ONNX Runtime session
        self.session = None
        if self.model_path and os.path.exists(self.model_path):
            try:
                # Create inference session
                sess_options = ort.SessionOptions()
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                
                providers = [provider]
                # Add CUDA provider if available (for GPU acceleration)
                if provider == "CPUExecutionProvider":
                    try:
                        providers.append("CUDAExecutionProvider")
                    except:
                        pass
                
                self.session = ort.InferenceSession(
                    self.model_path,
                    sess_options=sess_options,
                    providers=providers
                )
                logger.info(f"Loaded ONNX model: {self.model_path}")
                logger.info(f"Available providers: {self.session.get_providers()}")
            except Exception as e:
                logger.error(f"Failed to load ONNX model {self.model_path}: {e}")
                self.session = None
    
    def tokenize(self, text: str, max_length: int = 512) -> Dict[str, np.ndarray]:
        """
        Tokenize text using Hugging Face tokenizer.
        
        Args:
            text: Input text to tokenize
            max_length: Maximum sequence length
        
        Returns:
            Dictionary with 'input_ids' and 'attention_mask' as numpy arrays
        """
        if not self.tokenizer:
            raise ValueError("Tokenizer not initialized")
        
        # Tokenize text
        encoded = self.tokenizer(
            text,
            max_length=max_length,
            padding="max_length",
            truncation=True,
            return_tensors="np"
        )
        
        return {
            "input_ids": encoded["input_ids"].astype(np.int64),
            "attention_mask": encoded["attention_mask"].astype(np.int64)
        }
    
    def infer(self, input_ids: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        """
        Run ONNX inference.
        
        Args:
            input_ids: Token IDs from tokenizer
            attention_mask: Attention mask from tokenizer
        
        Returns:
            Model output (logits or probabilities)
        """
        if not self.session:
            raise ValueError("ONNX session not initialized")
        
        # Get input names from model
        input_names = [input.name for input in self.session.get_inputs()]
        
        # Prepare inputs
        inputs = {}
        if "input_ids" in input_names:
            inputs["input_ids"] = input_ids
        if "attention_mask" in input_names:
            inputs["attention_mask"] = attention_mask
        
        # Run inference
        outputs = self.session.run(None, inputs)
        
        return outputs[0]  # Return first output
    
    def classify(
        self,
        prompt: str,
        max_length: int = 512,
        temperature: float = 0.1
    ) -> Optional[Dict[str, any]]:
        """
        Classify email using ONNX model.
        
        Args:
            prompt: Classification prompt
            max_length: Maximum sequence length
            temperature: Sampling temperature (lower = more deterministic)
        
        Returns:
            Classification result with status, confidence, and reason
        """
        if not self.session or not self.tokenizer:
            logger.warning("ONNX model or tokenizer not available. Returning None.")
            return None
        
        try:
            # Tokenize
            tokenized = self.tokenize(prompt, max_length=max_length)
            
            # Run inference
            logits = self.infer(
                tokenized["input_ids"],
                tokenized["attention_mask"]
            )
            
            # Process output (assuming classification head)
            # This is model-specific - adjust based on your model architecture
            if len(logits.shape) == 2:
                # Apply softmax for probabilities
                probs = self._softmax(logits[0], temperature=temperature)
                
                # Get predicted class
                predicted_idx = np.argmax(probs)
                confidence = float(probs[predicted_idx])
                
                # Map to status (this is model-specific)
                status_map = {
                    0: "ACTIVE",
                    1: "INTERVIEW",
                    2: "REJECTED",
                    3: "OFFER",
                    4: "GHOSTED",
                    5: "WITHDRAWN"
                }
                
                status = status_map.get(predicted_idx, "ACTIVE")
                
                # Generate reason
                reason = f"Classified as {status} with {confidence:.2f} confidence"
                
                return {
                    "status": status,
                    "confidence": confidence,
                    "reason": reason
                }
            else:
                logger.warning(f"Unexpected logits shape: {logits.shape}")
                return None
                
        except Exception as e:
            logger.error(f"ONNX inference failed: {e}")
            return None
    
    def _softmax(self, x: np.ndarray, temperature: float = 1.0) -> np.ndarray:
        """Apply softmax with temperature."""
        x = x / temperature
        exp_x = np.exp(x - np.max(x))  # Numerical stability
        return exp_x / np.sum(exp_x)
    
    def is_available(self) -> bool:
        """Check if ONNX inference is available."""
        return self.session is not None and self.tokenizer is not None


def create_onnx_inference(
    model_path: Optional[str] = None,
    tokenizer_name: Optional[str] = None
) -> Optional[ONNXLLMInference]:
    """
    Factory function to create ONNX inference instance.
    
    Args:
        model_path: Path to ONNX model file
        tokenizer_name: Hugging Face tokenizer name
    
    Returns:
        ONNXLLMInference instance or None if not available
    """
    try:
        return ONNXLLMInference(model_path=model_path, tokenizer_name=tokenizer_name)
    except Exception as e:
        logger.warning(f"Failed to create ONNX inference: {e}")
        return None
