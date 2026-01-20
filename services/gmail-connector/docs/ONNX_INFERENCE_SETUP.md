# ONNX Runtime Inference Setup

This document explains how to use ONNX Runtime + Hugging Face tokenizers for fast, local LLM inference in Layer 7 of the hybrid classification engine.

## Dependencies

All dependencies are already installed in `requirements.txt`:
- `onnxruntime>=1.16.0` - ONNX Runtime for inference
- `transformers>=4.35.0` - Hugging Face transformers library
- `tokenizers>=0.15.0` - Fast tokenization
- `numpy>=1.24.0` - Numerical operations

## Installation

Dependencies are automatically installed when building the Docker container. To install manually:

```bash
pip install onnxruntime transformers tokenizers numpy
```

## Usage

### 1. Enable ONNX Inference

Set environment variables:

```bash
USE_ONNX_INFERENCE=true
ONNX_MODEL_PATH=/path/to/model.onnx
ONNX_TOKENIZER_NAME=bert-base-uncased  # or your model's tokenizer
```

### 2. Model Requirements

Your ONNX model should:
- Accept `input_ids` and `attention_mask` as inputs
- Output logits or probabilities for classification
- Support sequence length up to 512 tokens

### 3. Integration with Hybrid Classifier

The `HybridClassifier` automatically uses ONNX inference if:
- `USE_ONNX_INFERENCE=true`
- `ONNX_MODEL_PATH` is set and file exists
- ONNX inference is successfully initialized

Otherwise, it falls back to HTTP-based LLM calls.

## Example

```python
from app.hybrid_classifier import HybridClassifier

# ONNX inference will be used if configured
classifier = HybridClassifier()

email_data = {
    "subject": "Interview",
    "snippet": "Schedule your interview",
    "body": "Let's schedule",
    "sender_domain": "company.com",
    "sender_email": "hr@company.com"
}

result = classifier.classify(email_data)
```

## Performance

ONNX inference is typically:
- **10-100x faster** than HTTP-based LLM calls
- **No network latency** (runs locally)
- **Lower memory usage** (optimized model)
- **Deterministic** (same input → same output)

## Platform-Specific Notes

### Apple Silicon (M1/M2/M3)

If you encounter issues with ONNX Runtime on Apple Silicon, you may need:

```bash
pip install onnxruntime-silicon
```

Or use the CPU provider which works on all platforms.

### CUDA/GPU Acceleration

ONNX Runtime automatically uses CUDA if available:

```python
# Will use CUDA if available, otherwise CPU
inference = ONNXLLMInference(
    model_path="model.onnx",
    tokenizer_name="bert-base-uncased",
    provider="CUDAExecutionProvider"  # Falls back to CPU if not available
)
```

## Model Conversion

To convert a PyTorch/TensorFlow model to ONNX:

```python
# Example: Convert Hugging Face model to ONNX
from transformers import AutoModel
import torch

model = AutoModel.from_pretrained("bert-base-uncased")
model.eval()

# Create dummy input
dummy_input = torch.randint(0, 1000, (1, 512))

# Export to ONNX
torch.onnx.export(
    model,
    dummy_input,
    "model.onnx",
    input_names=["input_ids", "attention_mask"],
    output_names=["logits"],
    dynamic_axes={
        "input_ids": {0: "batch_size", 1: "sequence_length"},
        "attention_mask": {0: "batch_size", 1: "sequence_length"},
        "logits": {0: "batch_size"}
    }
)
```

## Troubleshooting

### Issue: "onnxruntime not available"
**Solution**: Install with `pip install onnxruntime`

### Issue: Model not loading
**Solution**: Check that `ONNX_MODEL_PATH` points to a valid `.onnx` file

### Issue: Tokenizer not loading
**Solution**: Check that `ONNX_TOKENIZER_NAME` is a valid Hugging Face model name

### Issue: Slow inference
**Solution**: 
- Use GPU provider if available
- Optimize model with ONNX Runtime optimizations
- Reduce `max_length` parameter

## Configuration

Add to your `.env` or Docker environment:

```bash
# Enable ONNX inference
USE_ONNX_INFERENCE=true

# Model path (absolute or relative to app directory)
ONNX_MODEL_PATH=/app/models/email_classifier.onnx

# Tokenizer name (Hugging Face model name)
ONNX_TOKENIZER_NAME=bert-base-uncased

# Optional: Execution provider
ONNX_PROVIDER=CPUExecutionProvider  # or CUDAExecutionProvider
```
