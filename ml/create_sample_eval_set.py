"""
Create a sample evaluation set from training data.

This is a fallback option when the database isn't available.
It samples from the training CSVs to create a balanced eval set.

Usage:
    python ml/create_sample_eval_set.py [--output PATH] [--size N]
"""
import pandas as pd
import argparse
from pathlib import Path
from sklearn.model_selection import train_test_split

REJECTED_PATH = "data/rejection_gate/rejection_1000 - rejection_1000_strict.csv"
NOT_REJECTED_PATH = "data/rejection_gate/not_rejected_1000 - not_rejected_1000_strict.csv"
OUTPUT_PATH = "data/rejection_gate/eval_real.csv"


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
    parser = argparse.ArgumentParser(
        description="Create sample evaluation set from training data"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_PATH,
        help=f"Output CSV path (default: {OUTPUT_PATH})"
    )
    parser.add_argument(
        "--size",
        type=int,
        default=200,
        help="Number of samples per label (default: 200, total: 400)"
    )
    
    args = parser.parse_args()
    
    print("Creating sample evaluation set from training data...")
    print(f"  Rejected samples: {args.size}")
    print(f"  Not rejected samples: {args.size}")
    print(f"  Total: {args.size * 2}")
    
    # Load training data
    try:
        print(f"\nLoading {REJECTED_PATH}...")
        df_rejected = load_and_validate(REJECTED_PATH)
        print(f"  Loaded {len(df_rejected)} rows")
        
        print(f"\nLoading {NOT_REJECTED_PATH}...")
        df_not_rejected = load_and_validate(NOT_REJECTED_PATH)
        print(f"  Loaded {len(df_not_rejected)} rows")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nMake sure the training CSV files exist:")
        print(f"  - {REJECTED_PATH}")
        print(f"  - {NOT_REJECTED_PATH}")
        return
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    # Sample from each dataset
    n_rejected = min(args.size, len(df_rejected))
    n_not_rejected = min(args.size, len(df_not_rejected))
    
    df_rejected_sample = df_rejected.sample(n=n_rejected, random_state=42)
    df_not_rejected_sample = df_not_rejected.sample(n=n_not_rejected, random_state=42)
    
    # Rename label column to true_label
    df_rejected_sample = df_rejected_sample.rename(columns={"label": "true_label"})
    df_not_rejected_sample = df_not_rejected_sample.rename(columns={"label": "true_label"})
    
    # Combine and shuffle
    df_eval = pd.concat([df_rejected_sample, df_not_rejected_sample], ignore_index=True)
    df_eval = df_eval.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Select only required columns
    df_eval = df_eval[["subject", "snippet", "from_domain", "true_label"]]
    
    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save
    df_eval.to_csv(output_path, index=False, quoting=1)
    
    print(f"\n✅ Created sample evaluation set:")
    print(f"   Path: {output_path}")
    print(f"   Total rows: {len(df_eval)}")
    print(f"   REJECTED: {(df_eval['true_label'] == 'REJECTED').sum()}")
    print(f"   NOT_REJECTED: {(df_eval['true_label'] == 'NOT_REJECTED').sum()}")
    print(f"\n⚠️  Note: This is sampled from training data, not real inbox emails.")
    print(f"   For best results, use ml/generate_eval_set.py with your actual database.")
    print(f"\nNext step: Run 'python ml/eval_reject_gate.py' to evaluate the model")


if __name__ == "__main__":
    main()
