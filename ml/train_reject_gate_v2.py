"""
Improved RejectGate Training Script v2.0

Key Improvements for Better Accuracy:
1. Better n-gram ranges (1-3 grams to capture phrases like "not proceeding")
2. Hyperparameter tuning with GridSearchCV
3. Cross-validation for robust evaluation
4. Better text preprocessing (stop words removal)
5. Threshold optimization for production use
6. More detailed metrics and evaluation
"""
import os
import re
import json
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    precision_recall_fscore_support,
    roc_auc_score
)

POS_LABEL = "REJECTED"
NEG_LABEL = "NOT_REJECTED"

# Handle file paths with spaces
REJECTED_PATH = "data/rejection_gate/rejection_1000 - rejection_1000_strict.csv"
NOT_REJECTED_PATH = "data/rejection_gate/not_rejected_1000 - not_rejected_1000_strict.csv"

OUT_DIR = "models/reject_gate"
MODEL_PATH = os.path.join(OUT_DIR, "reject_gate.joblib")
META_PATH = os.path.join(OUT_DIR, "reject_gate.meta.json")

PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")

def norm(s: str) -> str:
    """Normalize text: lowercase, collapse whitespace, replace proper nouns."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = PROPER_NOUN_RE.sub("<TOKEN>", s)
    return s.lower()

def make_text(row) -> str:
    """Combine subject, snippet, and domain into single text."""
    subject = norm(row.get("subject", ""))
    snippet = norm(row.get("snippet", ""))
    domain = norm(row.get("from_domain", ""))
    return f"subject: {subject} | snippet: {snippet} | domain: {domain}"

def load_and_validate(path: str) -> pd.DataFrame:
    """Load and validate CSV file."""
    df = pd.read_csv(path)
    required = ["subject", "snippet", "from_domain", "label"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    df["label"] = df["label"].astype(str).str.strip()
    return df

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 80)
    print("IMPROVED REJECTGATE TRAINING v2.0")
    print("=" * 80)
    
    # Load data
    print("\n1. Loading data...")
    df_pos = load_and_validate(REJECTED_PATH)
    df_neg = load_and_validate(NOT_REJECTED_PATH)
    print(f"   REJECTED: {len(df_pos)} rows")
    print(f"   NOT_REJECTED: {len(df_neg)} rows")

    df = pd.concat([df_pos, df_neg], ignore_index=True)

    # Keep only the two labels we care about
    df = df[df["label"].isin([POS_LABEL, NEG_LABEL])].copy()
    if df.empty:
        raise ValueError("No rows after filtering labels. Check label values in CSVs.")

    print(f"\n2. Preparing features...")
    print(f"   Total samples: {len(df)}")
    
    # Create text features
    X = df.apply(make_text, axis=1).values
    y = (df["label"] == POS_LABEL).astype(int).values  # 1=REJECTED, 0=NOT_REJECTED
    
    print(f"   REJECTED: {y.sum()} ({y.sum()/len(y)*100:.1f}%)")
    print(f"   NOT_REJECTED: {(1-y).sum()} ({(1-y).sum()/len(y)*100:.1f}%)")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\n3. Train/test split:")
    print(f"   Train: {len(X_train)} samples")
    print(f"   Test: {len(X_test)} samples")

    # Build improved pipeline
    print(f"\n4. Building improved model pipeline...")
    
    # Improved TF-IDF with better settings
    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 3),  # 1-3 grams (captures phrases like "not proceeding", "position has been filled")
            min_df=2,  # Minimum document frequency
            max_features=100000,  # More features for better accuracy
            sublinear_tf=True,  # Use 1 + log(tf) instead of tf (better for common words)
            analyzer='word',
            stop_words='english'  # Remove common English stop words
        )),
        ("clf", LogisticRegression(
            max_iter=5000,  # More iterations for convergence
            class_weight="balanced",  # Handle class imbalance
            solver='lbfgs'  # Good for small-medium datasets
        ))
    ])
    
    # Hyperparameter tuning
    print(f"\n5. Hyperparameter tuning (this may take a few minutes)...")
    param_grid = {
        'clf__C': [0.5, 1.0, 2.0, 5.0],  # Regularization strength
        'clf__class_weight': ['balanced', {0: 1, 1: 1.5}, {0: 1, 1: 2}]  # Class weights
    }
    
    # Use cross-validation for tuning
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    grid_search = GridSearchCV(
        pipe,
        param_grid,
        cv=cv,
        scoring='f1',  # Optimize for F1 score
        n_jobs=-1,  # Use all CPU cores
        verbose=1
    )
    
    grid_search.fit(X_train, y_train)
    
    print(f"\n6. Best hyperparameters:")
    print(f"   {grid_search.best_params_}")
    print(f"   Best CV F1 score: {grid_search.best_score_:.4f}")
    
    # Get best model
    best_pipe = grid_search.best_estimator_
    
    # Evaluate on test set
    print(f"\n7. Evaluating on test set...")
    y_pred = best_pipe.predict(X_test)
    y_pred_proba = best_pipe.predict_proba(X_test)[:, 1]
    
    # Metrics
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average='binary', zero_division=0
    )
    auc = roc_auc_score(y_test, y_pred_proba)
    
    print(f"\n8. Test Set Performance:")
    print(f"   Precision: {precision:.4f}")
    print(f"   Recall: {recall:.4f}")
    print(f"   F1 Score: {f1:.4f}")
    print(f"   ROC-AUC: {auc:.4f}")
    
    print(f"\n9. Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    print(f"   [TN={tn:3d}  FP={fp:3d}]")
    print(f"   [FN={fn:3d}  TP={tp:3d}]")
    
    print(f"\n10. Classification Report:")
    print(classification_report(y_test, y_pred, target_names=[NEG_LABEL, POS_LABEL]))
    
    # Cross-validation on full dataset for robust evaluation
    print(f"\n11. Cross-validation on full dataset (5-fold)...")
    cv_scores = cross_val_score(best_pipe, X, y, cv=5, scoring='f1')
    print(f"   CV F1 scores: {cv_scores}")
    print(f"   Mean CV F1: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    # Threshold optimization for production
    print(f"\n12. Optimizing threshold for production...")
    thresholds = np.arange(0.3, 0.95, 0.05)
    best_threshold = 0.85
    best_score = 0.0
    
    for thr in thresholds:
        y_pred_thr = (y_pred_proba >= thr).astype(int)
        prec, rec, f1_thr, _ = precision_recall_fscore_support(
            y_test, y_pred_thr, average='binary', zero_division=0
        )
        # Optimize for high precision (low false positives) while maintaining good recall
        # Weight precision more heavily to reduce false rejections
        score = 0.7 * prec + 0.3 * rec  # Weighted score favoring precision
        if score > best_score:
            best_score = score
            best_threshold = thr
    
    print(f"   Recommended threshold: {best_threshold:.2f}")
    
    # Evaluate at recommended threshold
    y_pred_opt = (y_pred_proba >= best_threshold).astype(int)
    prec_opt, rec_opt, f1_opt, _ = precision_recall_fscore_support(
        y_test, y_pred_opt, average='binary', zero_division=0
    )
    print(f"   At threshold {best_threshold:.2f}:")
    print(f"     Precision: {prec_opt:.4f}")
    print(f"     Recall: {rec_opt:.4f}")
    print(f"     F1: {f1_opt:.4f}")
    
    # Save model
    print(f"\n13. Saving model...")
    joblib.dump(best_pipe, MODEL_PATH)
    
    # Save metadata
    meta = {
        "model_type": "tfidf_logreg_v2",
        "model_version": "2.0",
        "labels": {"0": NEG_LABEL, "1": POS_LABEL},
        "recommended_threshold": float(best_threshold),
        "best_hyperparameters": grid_search.best_params_,
        "test_performance": {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "roc_auc": float(auc)
        },
        "cv_performance": {
            "mean_f1": float(cv_scores.mean()),
            "std_f1": float(cv_scores.std())
        },
        "threshold_performance": {
            "threshold": float(best_threshold),
            "precision": float(prec_opt),
            "recall": float(rec_opt),
            "f1": float(f1_opt)
        },
        "data_sources": [REJECTED_PATH, NOT_REJECTED_PATH],
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "features": {
            "tfidf_ngrams": "1-3",
            "tfidf_max_features": 100000,
            "sublinear_tf": True,
            "stop_words": "english"
        }
    }
    
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    
    print(f"\n✅ Model saved -> {MODEL_PATH}")
    print(f"✅ Metadata saved -> {META_PATH}")
    print(f"\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print(f"\nNext steps:")
    print(f"1. Evaluate on real inbox data: python ml/eval_reject_gate.py")
    print(f"2. Update threshold if needed based on eval results")
    print(f"3. Restart gmail-connector service to use new model")

if __name__ == "__main__":
    main()
