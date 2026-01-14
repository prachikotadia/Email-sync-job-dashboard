# Job Email Filtering Implementation Status

## PART A - Token Refresh (COMPLETED)

### ✅ Changes Made:
1. **Tokeninfo made non-blocking** (`app/security/token_verification.py`):
   - Changed `verify_token_scopes()` to return `(bool, Optional[List[str]])` instead of raising
   - Returns `(False, None)` on failure, logs warning, continues
   - NEVER blocks sync - Gmail API 401 is authoritative

2. **OAuth refresh flow implemented** (`app/security/google_oauth.py`):
   - Created `refresh_access_token(refresh_token: str)` function
   - Calls Google OAuth token endpoint with refresh_token
   - Returns new access_token, expires_in, scope, token_type
   - Raises `ReauthRequiredError` on failure

### ⚠️ TODO:
- Update `fetch_emails_from_gmail()` to:
  - Remove tokeninfo blocking checks
  - Call Gmail API directly
  - On 401: refresh token, persist, retry once
  - On refresh failure: return 401 "Re-auth required"

## PART B - Strict Filtering (IN PROGRESS)

### ✅ Changes Made:
1. **Strict Gmail query** (`app/filters/query_builder.py`):
   - Updated to use `build_job_gmail_query()` with extremely strict phrases
   - Only includes strong phrases: "thank you for applying", "application received", etc.
   - Hard exclusions: unsubscribe, newsletter, alert, jobs, etc.
   - Time-bounded: `newer_than:{days}d`

2. **Deterministic classifier** (`app/services/email_classifier.py`):
   - Created `EmailCategory` enum with 7 categories
   - Allow rules with points (4-5 points each)
   - Deny rules (hard reject)
   - Returns category, score, allow_hits, deny_hits, stored

3. **Config flags added** (`app/config.py`):
   - `GMAIL_QUERY_DAYS=30`
   - `GMAIL_MAX_RESULTS=50`
   - `STORE_CATEGORIES="APPLICATION_CONFIRMATION,INTERVIEW,REJECTION,OFFER"`

### ⚠️ TODO:
- Update `fetch_emails_from_gmail()` to use refresh flow
- Update sync flow to use new classifier
- Add structured logging for every email
- Implement category-based storage filtering
- Add unit tests

## Next Steps

1. Refactor `fetch_emails_from_gmail()` to remove tokeninfo blocking
2. Implement Gmail API retry with refresh on 401
3. Update sync flow to use deterministic classifier
4. Add structured logging
5. Add unit tests
