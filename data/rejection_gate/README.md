# RejectGate Evaluation Set

## Prerequisites

Install required dependencies for ML scripts:

```bash
# Install ML script dependencies
pip install -r ml/requirements.txt

# Or install individually:
pip install psycopg2-binary pandas scikit-learn joblib sqlalchemy
```

## Creating the Evaluation Set

Create `eval_real.csv` with ~200 rows from your actual fetched emails.

**Quick Start (if database isn't available):**
```bash
# Create sample eval set from training data (fallback option)
python ml/create_sample_eval_set.py
```

This creates a balanced eval set from your training CSVs. For best results, use the database method below.

### Required Columns:
- `subject`: Email subject line
- `snippet`: Email snippet/preview text
- `from_domain`: Sender domain (e.g., "recruiting.company.com")
- `true_label`: Either `REJECTED` or `NOT_REJECTED`

### Example:
```csv
subject,snippet,from_domain,true_label
"Application Status","Thank you for your interest. Unfortunately...",recruiting.company.com,REJECTED
"Next Steps","We'd like to schedule an interview...",ats.com,NOT_REJECTED
```

### How to Create:

**Option 1: Generate from Database (Recommended)**

Use the helper script to automatically extract from your database:

```bash
# Make sure Docker is running first:
docker-compose ps  # Check if db container is running
docker-compose up -d db  # Start database if not running

# Generate balanced eval set (default: 200 rows, 50% REJECTED, 50% NOT_REJECTED)
python ml/generate_eval_set.py

# Specify user email
python ml/generate_eval_set.py --user-email your@email.com

# Custom limit
python ml/generate_eval_set.py --limit 300

# Don't balance labels
python ml/generate_eval_set.py --no-balance
```

The script will:
- Connect to your database (defaults to localhost:5433)
- Extract applications with subject, snippet, and domain
- Map category to true_label (REJECTED or NOT_REJECTED)
- Balance labels if possible
- Save to `data/rejection_gate/eval_real.csv`

**If database connection fails:**
- Make sure Docker containers are running: `docker-compose ps`
- Start the database: `docker-compose up -d db`
- Or use the fallback option below

**Option 2: Export from Database Manually**

```sql
SELECT 
    subject,
    snippet,
    CASE 
        WHEN from_email LIKE '%@%' THEN SPLIT_PART(from_email, '@', 2)
        ELSE company_domain
    END as from_domain,
    CASE 
        WHEN category = 'REJECTED' THEN 'REJECTED'
        ELSE 'NOT_REJECTED'
    END as true_label
FROM applications
WHERE user_id = YOUR_USER_ID
  AND subject IS NOT NULL
  AND snippet IS NOT NULL
LIMIT 200;
```

**Option 3: Manually label emails:**
   - Review emails from your actual inbox
   - Label each as `REJECTED` or `NOT_REJECTED`
   - Aim for ~50% REJECTED, 50% NOT_REJECTED for balanced evaluation

3. **Save as CSV:**
   - Save to `data/rejection_gate/eval_real.csv`
   - Ensure proper CSV escaping (quotes around fields with commas)

### Running Evaluation:

```bash
python ml/eval_reject_gate.py
```

The script will:
- Test multiple thresholds (0.50, 0.65, 0.75, 0.80, 0.85, 0.90, 0.95)
- Show precision, recall, F1, and false rejection rate for each
- Recommend the best threshold with <5% false rejection rate
- Provide detailed classification report

### Updating the Threshold:

After evaluation, update `models/reject_gate/reject_gate.meta.json`:

```json
{
  "recommended_threshold": 0.85
}
```

Then restart the gmail-connector service to use the new threshold.
