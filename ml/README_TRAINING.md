# RejectGate Model Training

## Quick Start

### Option 1: Train Improved Model (Recommended)

```bash
# Install dependencies
pip install -r ml/requirements.txt

# Train improved model
python ml/train_reject_gate_v2.py
```

### Option 2: Train in Docker

```bash
# Run training in gmail-connector container
docker-compose exec gmail-connector-service python ml/train_reject_gate_v2.py
```

## Model Versions

### v1.0 (Original)
- Basic TF-IDF (1-2 grams)
- Simple Logistic Regression
- Threshold: 0.85

### v2.0 (Improved - Recommended)
- Enhanced TF-IDF (1-3 grams) - captures phrases like "not proceeding"
- Hyperparameter tuning with GridSearchCV
- Cross-validation for robust evaluation
- Stop words removal
- Sublinear TF scaling
- Optimized threshold for production
- Better metrics and evaluation

## Improvements in v2.0

1. **Better N-grams**: 1-3 grams instead of 1-2 (captures rejection phrases)
2. **Hyperparameter Tuning**: Automatically finds best C and class_weight
3. **Cross-Validation**: 5-fold CV for robust performance estimation
4. **Stop Words**: Removes common English words for better signal
5. **Sublinear TF**: Uses log scaling for term frequency
6. **Threshold Optimization**: Finds optimal threshold for production use
7. **More Features**: 100K features instead of 250K (faster, still accurate)

## Expected Performance

With v2.0, you should see:
- **F1 Score**: > 0.90
- **Precision**: > 0.92 (low false positives)
- **Recall**: > 0.88 (catches most rejections)
- **ROC-AUC**: > 0.95

## After Training

1. **Evaluate on real data**:
   ```bash
   python ml/eval_reject_gate.py
   ```

2. **Update threshold** if needed (based on eval results)

3. **Restart service**:
   ```bash
   docker-compose restart gmail-connector-service
   ```

## Troubleshooting

### ModuleNotFoundError
Install dependencies:
```bash
pip install -r ml/requirements.txt
```

### Low Accuracy
- Check data quality in CSV files
- Ensure balanced dataset (similar counts of REJECTED and NOT_REJECTED)
- Try adjusting hyperparameters in the script

### Model Not Loading
- Check that `models/reject_gate/reject_gate.joblib` exists
- Verify Docker volume mount in `docker-compose.yml`
- Check logs: `docker-compose logs gmail-connector-service | grep RejectGate`
