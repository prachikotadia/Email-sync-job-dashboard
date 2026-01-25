"""
Generate evaluation set from database applications.

Extracts subject, snippet, and domain from existing applications
and creates eval_real.csv for RejectGate evaluation.

Usage:
    python ml/generate_eval_set.py [--user-email EMAIL] [--limit N] [--output PATH]
"""
import os
import sys
import pandas as pd
import argparse
from pathlib import Path
from urllib.parse import urlparse

# Set up database URL before importing database module
# Default to localhost:5433 (host port) for local runs
default_db_url = "postgresql://jobpulse:jobpulse_password@localhost:5433/jobpulse_db"
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = default_db_url
elif "db:5432" in os.environ.get("DATABASE_URL", ""):
    # Convert Docker container URL to localhost port
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace("db:5432", "localhost:5433")

# Add services/gmail-connector to path to import database models
project_root = Path(__file__).parent.parent
gmail_connector_path = project_root / "services" / "gmail-connector"
sys.path.insert(0, str(gmail_connector_path))

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 is required for database access.")
    print("\nInstall it with:")
    print("  pip install psycopg2-binary")
    print("\nOr install all ML dependencies:")
    print("  pip install psycopg2-binary pandas scikit-learn joblib sqlalchemy")
    sys.exit(1)

try:
    from app.database import SessionLocal, Application, User
except ImportError as e:
    print(f"Error: Could not import database models: {e}")
    print(f"Make sure you're running from the project root: {project_root}")
    print(f"Expected path: {gmail_connector_path}")
    print("\nAlso ensure you have the required dependencies:")
    print("  pip install psycopg2-binary pandas scikit-learn joblib sqlalchemy")
    sys.exit(1)


def extract_domain_from_email(email: str) -> str:
    """Extract domain from email address."""
    if not email:
        return ""
    if "@" in email:
        return email.split("@")[1].lower()
    return email.lower()


def generate_eval_set(
    user_email: str = None,
    limit: int = 200,
    output_path: str = "data/rejection_gate/eval_real.csv",
    balance: bool = True
):
    """
    Generate evaluation set from database.
    
    Args:
        user_email: User email to filter by (optional, uses first user if not provided)
        limit: Maximum number of rows to export
        output_path: Output CSV path
        balance: If True, try to balance REJECTED and NOT_REJECTED labels
    """
    try:
        db = SessionLocal()
        # Test connection (simple query to verify connection works)
        _ = db.query(User).limit(1).all()
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Docker containers are running:")
        print("   docker-compose ps")
        print("2. Start the database if it's not running:")
        print("   docker-compose up -d db")
        print("3. Check if database is accessible on localhost:5433")
        print("4. Or set DATABASE_URL environment variable:")
        print("   export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        print("\n💡 Alternative: Create a sample eval set from training data:")
        print("   python ml/create_sample_eval_set.py")
        return
    
    try:
        
        # Get user
        if user_email:
            user = db.query(User).filter(User.email == user_email).first()
            if not user:
                print(f"Error: User with email '{user_email}' not found.")
                return
        else:
            user = db.query(User).first()
            if not user:
                print("Error: No users found in database.")
                print("Please sync some emails first or specify --user-email")
                return
        
        print(f"Using user: {user.email} (ID: {user.id})")
        
        # Query applications
        query = db.query(Application).filter(Application.user_id == user.id)
        
        # Filter to only applications with required fields
        query = query.filter(
            Application.subject.isnot(None),
            Application.subject != "",
            Application.snippet.isnot(None)
        )
        
        # Get all applications
        all_apps = query.all()
        
        if not all_apps:
            print("Error: No applications found with required fields (subject, snippet).")
            print("Please sync some emails first.")
            return
        
        print(f"Found {len(all_apps)} applications with required fields")
        
        # Prepare data
        data = []
        for app in all_apps:
            # Extract domain from from_email
            domain = extract_domain_from_email(app.from_email) if app.from_email else ""
            if not domain and app.company_domain:
                domain = app.company_domain.lower()
            
            # Map category to true_label
            category = app.category.upper() if app.category else "ACTIVE"
            if category == "REJECTED":
                true_label = "REJECTED"
            else:
                true_label = "NOT_REJECTED"
            
            data.append({
                "subject": app.subject or "",
                "snippet": app.snippet or "",
                "from_domain": domain,
                "true_label": true_label
            })
        
        df = pd.DataFrame(data)
        
        # Show distribution
        print(f"\nLabel distribution:")
        print(df["true_label"].value_counts())
        
        # Balance if requested
        if balance:
            rejected = df[df["true_label"] == "REJECTED"]
            not_rejected = df[df["true_label"] == "NOT_REJECTED"]
            
            min_count = min(len(rejected), len(not_rejected))
            target_per_label = min(limit // 2, min_count)
            
            if target_per_label > 0:
                # Sample balanced
                rejected_sample = rejected.sample(n=min(target_per_label, len(rejected)), random_state=42)
                not_rejected_sample = not_rejected.sample(n=min(target_per_label, len(not_rejected)), random_state=42)
                df = pd.concat([rejected_sample, not_rejected_sample], ignore_index=True)
                df = df.sample(frac=1, random_state=42).reset_index(drop=True)  # Shuffle
                print(f"\nBalanced to {len(df)} rows ({len(rejected_sample)} REJECTED, {len(not_rejected_sample)} NOT_REJECTED)")
            else:
                # Not enough data to balance, just take limit
                df = df.head(limit)
                print(f"\nLimited to {len(df)} rows (could not balance)")
        else:
            # Just take limit
            df = df.head(limit)
            print(f"\nLimited to {len(df)} rows")
        
        # Create output directory
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        df.to_csv(output_path, index=False, quoting=1)  # quoting=1 means QUOTE_ALL
        
        print(f"\n✅ Saved evaluation set to: {output_path}")
        print(f"   Total rows: {len(df)}")
        print(f"   REJECTED: {(df['true_label'] == 'REJECTED').sum()}")
        print(f"   NOT_REJECTED: {(df['true_label'] == 'NOT_REJECTED').sum()}")
        print(f"\nNext step: Run 'python ml/eval_reject_gate.py' to evaluate the model")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Alternative: Create a sample eval set from training data:")
        print("   python ml/create_sample_eval_set.py")
    finally:
        if 'db' in locals():
            db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate evaluation set from database applications"
    )
    parser.add_argument(
        "--user-email",
        type=str,
        help="User email to filter by (optional, uses first user if not provided)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of rows to export (default: 200)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/rejection_gate/eval_real.csv",
        help="Output CSV path (default: data/rejection_gate/eval_real.csv)"
    )
    parser.add_argument(
        "--no-balance",
        action="store_true",
        help="Don't balance REJECTED and NOT_REJECTED labels"
    )
    
    args = parser.parse_args()
    
    # Database URL is already set at module level
    db_url = os.getenv("DATABASE_URL", "postgresql://jobpulse:jobpulse_password@localhost:5433/jobpulse_db")
    print(f"Connecting to database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    
    generate_eval_set(
        user_email=args.user_email,
        limit=args.limit,
        output_path=args.output,
        balance=not args.no_balance
    )


if __name__ == "__main__":
    main()
