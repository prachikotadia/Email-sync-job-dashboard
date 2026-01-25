import os
import re
import json
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix

POS_LABEL = "REJECTED"
NEG_LABEL = "NOT_REJECTED"

# Handle file paths with spaces
REJECTED_PATH = "data/rejection_gate/rejection_1000 - rejection_1000_strict.csv"
NOT_REJECTED_PATH = "data/rejection_gate/not_rejected_1000 - not_rejected_1000_strict.csv"

OUT_DIR = "models/reject_gate"
MODEL_PATH = os.path.join(OUT_DIR, "reject_gate.joblib")
META_PATH  = os.path.join(OUT_DIR, "reject_gate.meta.json")

PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")

def norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = PROPER_NOUN_RE.sub("<TOKEN>", s)  # optional: reduces company-name overfitting
    return s.lower()

def make_text(row) -> str:
    subject = norm(row.get("subject", ""))
    snippet = norm(row.get("snippet", ""))
    domain  = norm(row.get("from_domain", ""))
    return f"subject: {subject} | snippet: {snippet} | domain: {domain}"

def load_and_validate(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["subject", "snippet", "from_domain", "label"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    df["label"] = df["label"].astype(str).str.strip()
    return df

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df_pos = load_and_validate(REJECTED_PATH)
    df_neg = load_and_validate(NOT_REJECTED_PATH)

    df = pd.concat([df_pos, df_neg], ignore_index=True)

    # Keep only the two labels we care about
    df = df[df["label"].isin([POS_LABEL, NEG_LABEL])].copy()
    if df.empty:
        raise ValueError("No rows after filtering labels. Check label values in CSVs.")

    X = df.apply(make_text, axis=1).values
    y = (df["label"] == POS_LABEL).astype(int).values  # 1=REJECTED, 0=NOT_REJECTED

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=250000)),
        ("clf", LogisticRegression(max_iter=2500, class_weight="balanced")),
    ])

    pipe.fit(X_train, y_train)

    y_pred = pipe.predict(X_test)

    print("\nConfusion matrix (rows=true, cols=pred):")
    print(confusion_matrix(y_test, y_pred))
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, target_names=[NEG_LABEL, POS_LABEL]))

    joblib.dump(pipe, MODEL_PATH)

    meta = {
        "model_type": "tfidf_logreg",
        "labels": {"0": NEG_LABEL, "1": POS_LABEL},
        # Start strict (reduce false rejects); tune later with real inbox eval set
        "recommended_threshold": 0.85,
        "data_sources": [REJECTED_PATH, NOT_REJECTED_PATH],
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"\nSaved model -> {MODEL_PATH}")
    print(f"Saved meta  -> {META_PATH}")

if __name__ == "__main__":
    main()
