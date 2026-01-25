"""
Evaluate RejectGate model on real inbox evaluation set.

Tests multiple thresholds to find optimal balance:
- Near-zero false rejections (precision)
- High recall (catch most rejections)

Usage:
    python ml/eval_reject_gate.py

Expected eval file format (data/rejection_gate/eval_real.csv):
    subject,snippet,from_domain,true_label
    "Application Status","Thank you for...",company.com,REJECTED
    "Next Steps","We'd like to...",ats.com,NOT_REJECTED
"""
import pandas as pd
import joblib
import re
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support
)
from pathlib import Path

MODEL_PATH = "models/reject_gate/reject_gate.joblib"
EVAL_PATH = "data/rejection_gate/eval_real.csv"

THRESHOLDS = [0.50, 0.65, 0.75, 0.80, 0.85, 0.90, 0.95]

PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")

def norm(s: str) -> str:
    """Normalize text (same as training script)."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = PROPER_NOUN_RE.sub("<TOKEN>", s)
    return s.lower()

def build_text(df):
    """Build text features from dataframe (same format as training)."""
    subject = df["subject"].fillna("").astype(str).apply(norm)
    snippet = df["snippet"].fillna("").astype(str).apply(norm)
    domain = df["from_domain"].fillna("").astype(str).apply(norm)
    return (
        "subject: " + subject +
        " | snippet: " + snippet +
        " | domain: " + domain
    )

def main():
    """Evaluate model at multiple thresholds and print metrics."""
    # Check files exist
    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}\n"
            "Please run ml/train_reject_gate.py first."
        )
    
    if not Path(EVAL_PATH).exists():
        raise FileNotFoundError(
            f"Evaluation set not found: {EVAL_PATH}\n"
            "Please create eval_real.csv with columns: subject,snippet,from_domain,true_label\n"
            "Use ~200 rows from your actual fetched emails."
        )
    
    # Load data
    print(f"Loading evaluation set from: {EVAL_PATH}")
    df = pd.read_csv(EVAL_PATH)
    
    # Validate columns
    required = ["subject", "snippet", "from_domain", "true_label"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in eval file: {missing}")
    
    # Validate labels
    df["true_label"] = df["true_label"].astype(str).str.strip()
    valid_labels = {"REJECTED", "NOT_REJECTED"}
    invalid_labels = set(df["true_label"].unique()) - valid_labels
    if invalid_labels:
        raise ValueError(
            f"Invalid labels found: {invalid_labels}\n"
            f"Expected only: {valid_labels}"
        )
    
    print(f"Loaded {len(df)} evaluation examples")
    print(f"  REJECTED: {(df['true_label'] == 'REJECTED').sum()}")
    print(f"  NOT_REJECTED: {(df['true_label'] == 'NOT_REJECTED').sum()}")
    
    # Load model
    print(f"\nLoading model from: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    
    # Build features (same format as training)
    X = build_text(df)
    y_true = (df["true_label"] == "REJECTED").astype(int).values
    
    # Get predictions
    print("\nComputing predictions...")
    p = model.predict_proba(X)[:, 1]  # Probability of REJECTED (class 1)
    
    print("\n" + "="*80)
    print("THRESHOLD EVALUATION")
    print("="*80)
    print("\nFormat: THR=threshold | precision | recall | f1 | confusion_matrix")
    print("Confusion matrix: [TN FP]")
    print("                  [FN TP]")
    print("="*80)
    
    best_threshold = None
    best_f1 = -1
    best_metrics = None
    
    results = []
    
    for thr in THRESHOLDS:
        y_pred = (p >= thr).astype(int)
        
        # Calculate metrics
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="binary", zero_division=0
        )
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        
        # False rejection rate (FP / (FP + TN)) - rejections we incorrectly flagged
        false_rejection_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        results.append({
            "threshold": thr,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "false_rejection_rate": false_rejection_rate,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn
        })
        
        print(f"\nTHR={thr:.2f}  precision={prec:.3f}  recall={rec:.3f}  f1={f1:.3f}  false_reject_rate={false_rejection_rate:.3f}")
        print(f"Confusion Matrix:")
        print(f"  [TN={tn:3d}  FP={fp:3d}]")
        print(f"  [FN={fn:3d}  TP={tp:3d}]")
        
        # Track best F1
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thr
            best_metrics = {
                "precision": prec,
                "recall": rec,
                "f1": f1,
                "false_rejection_rate": false_rejection_rate
            }
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    # Find threshold with near-zero false rejections (FP rate < 0.05)
    low_fp_thresholds = [r for r in results if r["false_rejection_rate"] < 0.05]
    if low_fp_thresholds:
        best_low_fp = max(low_fp_thresholds, key=lambda x: x["recall"])
        print(f"\n✅ Best threshold with <5% false rejection rate:")
        print(f"   THR={best_low_fp['threshold']:.2f}")
        print(f"   precision={best_low_fp['precision']:.3f}")
        print(f"   recall={best_low_fp['recall']:.3f}")
        print(f"   f1={best_low_fp['f1']:.3f}")
        print(f"   false_rejection_rate={best_low_fp['false_rejection_rate']:.3f}")
        print(f"\n   → Update recommended_threshold in models/reject_gate/reject_gate.meta.json")
    else:
        print("\n⚠️  No threshold found with <5% false rejection rate")
        print("   Consider retraining with more balanced data or adjusting thresholds")
    
    # Best F1 overall
    print(f"\n📊 Best F1 score overall:")
    print(f"   THR={best_threshold:.2f}")
    print(f"   precision={best_metrics['precision']:.3f}")
    print(f"   recall={best_metrics['recall']:.3f}")
    print(f"   f1={best_metrics['f1']:.3f}")
    print(f"   false_rejection_rate={best_metrics['false_rejection_rate']:.3f}")
    
    # Detailed classification report at recommended threshold
    recommended_thr = best_low_fp['threshold'] if low_fp_thresholds else best_threshold
    y_pred_recommended = (p >= recommended_thr).astype(int)
    
    print("\n" + "="*80)
    print(f"DETAILED CLASSIFICATION REPORT (THR={recommended_thr:.2f})")
    print("="*80)
    print(classification_report(
        y_true,
        y_pred_recommended,
        target_names=["NOT_REJECTED", "REJECTED"],
        zero_division=0
    ))
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"1. Review metrics above")
    print(f"2. If satisfied, update recommended_threshold in models/reject_gate/reject_gate.meta.json")
    print(f"3. Recommended threshold: {recommended_thr:.2f}")
    print(f"4. Restart gmail-connector service to use new threshold")

if __name__ == "__main__":
    main()
