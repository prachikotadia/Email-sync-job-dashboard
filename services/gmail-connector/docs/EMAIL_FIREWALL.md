# Email Firewall: How to Tune and Debug

## Overview

The Email Firewall is a **pre-classification filter** that blocks non-job emails (Render confirmations, Google security alerts, OTPs, promos, support tickets, newsletters) **before** they enter the job classification pipeline.

## Architecture

The firewall runs **FIRST** in the processing pipeline:

1. **Firewall** (blocks non-job emails)
2. RejectGate (fast rejection detection)
3. OfferGate
4. InterviewGate
5. Applied rules/model
6. Else → OTHER/ACTIVE

## Configuration

The firewall is configured via `config/email_firewall.yaml`. This file contains:

### DENY Rules (Block Immediately)

- **Exact domains**: `render.com`, `netlify.com`, `github.com`, `stripe.com`, etc.
- **Substring domains**: Any domain containing `auth`, `login`, `security`, `billing`, `newsletter`, etc.
- **Keywords**: Subject or snippet containing `otp`, `verification`, `deployment`, `invoice`, `ticket`, etc.

### ALLOW Rules (Job Pipeline Entry)

- **ATS domains**: `greenhouse.io`, `lever.co`, `workday.com`, etc.
- **Job keywords**: `application`, `candidate`, `position`, `role`, `interview`, `offer`, etc.
- **Sender patterns**: `recruiting@`, `talent@`, `careers@`, `jobs@`, etc.

### Strong Job Override

If an email matches deny rules BUT contains unambiguous job decision phrases (e.g., "we regret to inform you regarding your application"), it will be allowed through.

## Decision Logic

1. **Check DENY rules** (exact domains → substring domains → keywords)
2. If denied, check **Strong Job Override**
3. If still denied, return `DENY` immediately
4. If not denied, check **ALLOW rules** (ATS domains → job keywords → sender patterns)
5. If any allow rule matches → `ALLOW`
6. If no allow rules match → `DENY` (conservative default)

## Database Fields

Every processed email has firewall information stored:

- `firewall_decision`: `ALLOW` or `DENY`
- `firewall_category`: `NON_JOB_AUTH`, `NON_JOB_PROMO`, `NON_JOB_SUPPORT`, `NON_JOB_BILLING`, `NON_JOB_DEPLOY`, `UNKNOWN`, or `JOB`
- `firewall_reason`: Human-readable explanation
- `firewall_matched_rules`: List of matched rule IDs (e.g., `["domain_exact:render.com", "keyword:otp"]`)
- `is_job_email`: Boolean derived from `firewall_decision`

## Debugging

### Debug Endpoint

Use the debug endpoint to inspect firewall decisions:

```bash
GET /debug/email/{message_id}?user_id={user_email}
```

Returns:
```json
{
  "message_id": "...",
  "subject": "...",
  "snippet": "...",
  "from_email": "...",
  "firewall": {
    "decision": "DENY",
    "category": "NON_JOB_AUTH",
    "reason": "Blocked by firewall: domain_exact:accounts.google.com, keyword:security alert",
    "matched_rules": ["domain_exact:accounts.google.com", "keyword:security alert"],
    "is_job_email": false
  },
  "classification": {
    "category": "IGNORED",
    ...
  }
}
```

### Sync Logs

Sync logs include firewall counts:

```
Fetched: 1000 emails. Job-related candidates: 500.
Firewall: 450 allowed, 50 denied.
APPLIED: 200, REJECTED: 150, INTERVIEW: 50, ...
```

### Filtered Emails

Emails blocked by the firewall are saved with `category="IGNORED"` and do NOT appear in the job dashboard. They are stored in the database for debugging/transparency.

## Tuning the Firewall

### Adding New Deny Rules

Edit `config/email_firewall.yaml`:

```yaml
firewall:
  deny:
    domains_exact:
      - new-spam-domain.com
    keywords:
      - "new spam phrase"
```

**No code changes required** - just restart the service to reload config.

### Adjusting Allow Rules

To allow more emails through, add to allow rules:

```yaml
firewall:
  allow:
    ats_domains:
      - new-ats-platform.com
    job_keywords:
      - "new job phrase"
```

### Testing Changes

1. Update `config/email_firewall.yaml`
2. Restart `gmail-connector-service`:
   ```bash
   docker-compose restart gmail-connector-service
   ```
3. Run a test sync
4. Check debug endpoint for specific emails
5. Review sync logs for firewall counts

## Common Issues

### False Positives (Job emails being blocked)

1. Check debug endpoint: `GET /debug/email/{message_id}`
2. Review `firewall_matched_rules` to see which deny rule matched
3. Add exception to allow rules or strong job override phrases
4. Update config and restart service

### False Negatives (Non-job emails getting through)

1. Check debug endpoint to see why it was allowed
2. Add domain/keyword to deny rules
3. Update config and restart service

### Config Not Loading

- Ensure `config/email_firewall.yaml` exists in the project root
- Check Docker volume mounts in `docker-compose.yml`
- Verify file permissions
- Check service logs for config loading errors

## Best Practices

1. **Start conservative**: Default to DENY if unsure
2. **Monitor debug endpoint**: Regularly check why emails were filtered
3. **Update config incrementally**: Add rules one at a time and test
4. **Document exceptions**: If you add a strong job override, document why
5. **Review sync logs**: Monitor firewall counts to catch issues early

## Testing

Run the test suite:

```bash
cd services/gmail-connector
pytest tests/test_email_firewall.py -v
```

The test suite includes 25+ test cases covering:
- Render/Netlify deployments
- Google security alerts
- OTP/verification emails
- Newsletters/promos
- Billing/receipts
- Support tickets
- Real job emails
- ATS domains
- Strong job overrides
