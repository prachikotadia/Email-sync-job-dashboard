# 🧪 TESTING GUIDE - Production-Grade Gmail Sync

## ✅ IMPLEMENTATION COMPLETE

All 9 requirements have been implemented. Use this guide to verify functionality.

## TEST 1: Sync with 0.9 Confidence Threshold

### Steps:
1. Open frontend: http://localhost:5173
2. Login with Google OAuth
3. Click "Sync Emails" button
4. Watch sync progress

### Expected Behavior:
- **Fetches**: Up to 1200 most recent emails (newest first)
- **Classifies**: Only emails with confidence >= 0.9 are stored
- **Stores**: All classified emails in database
- **Logs**: Comprehensive stats with error detection

### Check Logs For:
```
[SYNC STATS] RULE 11 - COMPREHENSIVE SUMMARY
Total fetched: X
Pages fetched: Y
Skipped count: Z
Accepted count: A
Applied: B
Rejected: C
Interview: D
Offer: E
Accepted: F
Withdrawn: G
Other_Job_Update: H
```

### Verify:
- ✅ Confidence threshold is 0.9 (stricter than before)
- ✅ Only high-confidence emails are stored
- ✅ Status breakdown includes ACCEPTED, WITHDRAWN, OTHER_JOB_UPDATE

## TEST 2: Status Classification

### Expected Statuses:
- **APPLIED**: Application confirmations
- **REJECTED**: Rejection emails (highest priority)
- **INTERVIEW**: Interview invitations
- **OFFER**: Job offers
- **ACCEPTED**: Offer acceptances
- **WITHDRAWN**: Application withdrawals
- **GHOSTED**: No response (inferred)
- **OTHER_JOB_UPDATE**: Other job-related updates

### Priority Rules:
1. REJECTED overrides everything
2. INTERVIEW overrides APPLIED
3. OFFER overrides INTERVIEW
4. ACCEPTED overrides OFFER

### Verify:
- ✅ Each email has exactly ONE status
- ✅ Priority rules are enforced
- ✅ Status mapping is correct in logs

## TEST 3: Company Extraction

### Expected Behavior:
- Company extracted with confidence >= 0.85
- If confidence < 0.85, marked as "UNKNOWN"
- Priority: Signature → Platform → Domain → NLP

### Check Logs For:
```
[COMPANY] Low confidence (X.XX < 0.85) for 'CompanyName', marking as UNKNOWN
```

### Verify:
- ✅ No empty company names
- ✅ "UNKNOWN" used when confidence < 0.85
- ✅ Company names are normalized

## TEST 4: Dashboard Visibility

### Steps:
1. After sync completes, check dashboard
2. Verify all applications are visible
3. Check browser console for logs

### Expected Behavior:
- **Shows ALL applications** for the authenticated user
- **No limit**: All stored applications visible
- **Most recent first**: Sorted by last_email_date DESC
- **userId scoped**: Only shows applications for logged-in user

### Check Browser Console:
```
📊 Dashboard State: {
  applicationsCount: X,
  applications: [...],
  metrics: {...},
  loading: false,
  hasData: true
}
```

### Verify:
- ✅ Count matches stored count from sync logs
- ✅ All applications visible (no missing)
- ✅ Sorted by most recent first
- ✅ Only shows user's own applications

## TEST 5: Multi-User Support

### Steps:
1. Login as User A, sync emails
2. Logout, login as User B
3. Verify User B only sees their own applications

### Expected Behavior:
- User A sees only User A's applications
- User B sees only User B's applications
- No cross-user data leakage

### Verify:
- ✅ userId filtering works correctly
- ✅ No shared state between users
- ✅ Each user's data is isolated

## TEST 6: Logging & Error Detection

### Check Logs For:
```
[SYNC COMPLETE] FINAL VERIFICATION
Fetched: X
Classified as job-related: Y
Stored in DB: Z
Applications created/updated: A
Status breakdown: ...
```

### Error Detection:
- ❌ ERROR if stored count != classified count
- ❌ ERROR if results count != DB count
- ❌ ERROR if fetched != accepted + rejected

### Verify:
- ✅ All numbers match
- ✅ No ERROR logs (unless there's a real issue)
- ✅ Comprehensive breakdown logged

## COMMON ISSUES & SOLUTIONS

### Issue: Applications not visible in dashboard
**Solution**: 
- Check userId filtering is working
- Verify X-User-Id header is being sent
- Check browser console for errors

### Issue: Too few emails stored
**Solution**:
- Confidence threshold is now 0.9 (stricter)
- This is expected - only high-confidence emails are stored
- Check logs for rejection reasons

### Issue: Status classification incorrect
**Solution**:
- Check priority rules are enforced
- Verify status mapping in gmail_sync.py
- Check logs for classification reasons

## STATUS

**READY FOR TESTING** ✅

All requirements implemented. Follow this guide to verify functionality.
