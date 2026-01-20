# ONNX Model Files

This directory contains the ONNX model files for email classification.

## Required Files

Place the following files in this directory:

- **`model_quantized.onnx`** - Quantized ONNX model (use for speed + lower RAM)
- **`config.json`** - Model configuration
- **`tokenizer.json`** - Tokenizer file
- **`tokenizer_config.json`** - Tokenizer configuration
- **`vocab.txt`** - Vocabulary file

## Important Notes

⚠️ **DO NOT load from Hugging Face URL in production!**

All model files must be stored locally in this directory. The classifier uses `local_files_only=True` to ensure models are never downloaded from Hugging Face Hub in production.

## Usage

The `HFONNXClassifier` automatically loads from this directory:

```python
from app.services.classifier.hf_onnx_classifier import HFONNXClassifier

# Automatically loads from models/job_email/onnx/
classifier = HFONNXClassifier()

result = classifier.classify("Email subject and body...")
```

## Model Quantization

Use `model_quantized.onnx` for:
- **Speed**: Faster inference
- **Lower RAM**: Reduced memory usage
- **Production**: Optimized for deployment

## File Structure

```
models/
  job_email/
    onnx/
      model_quantized.onnx  ← Main model file
      config.json
      tokenizer.json
      tokenizer_config.json
      vocab.txt
```
