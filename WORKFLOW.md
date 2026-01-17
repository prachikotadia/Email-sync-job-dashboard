# JobPulse AI - Professional Workflow Documentation

This document is the **source-of-truth** for the JobPulse AI workflow. All development must strictly follow these rules.

## 0. NON-NEGOTIABLE PRINCIPLES (STRICT RULES)

### Docker is Mandatory
- ✅ No local installs
- ✅ No OS-specific commands
- ✅ Must work identically on macOS and Windows
- ✅ All services run in Docker containers

### Stateless by Email Account
- ✅ When user switches Gmail account → **ALL previous email data MUST BE DELETED**
- ✅ No cross-account leakage (privacy critical)
- ✅ Account switch triggers complete data wipe

### Fetch ALL Emails
- ✅ Not 50, not 1200, **100% of emails from first to last**
- ✅ Even 44,000+ emails must sync
- ✅ No hard limits, no early exits
- ✅ Paginate until `nextPageToken == null`

### Incremental + Real-Time
- ✅ First sync = full historical sync
- ✅ Every login = check for new emails
- ✅ New email received → must appear after sync
- ✅ Uses Gmail `historyId` for incremental syncs

### Only 5 Allowed Categories
1. **Applied**
2. **Rejected**
3. **Interview**
4. **Offer / Accepted**
5. **Ghosted**

Everything else → skipped (but counted)

### Dashboard Must Reflect Reality
- ✅ Counts must match database
- ✅ Logs must match fetched count
- ✅ No frontend limits
- ✅ No fake numbers

## 1. HIGH-LEVEL SYSTEM ARCHITECTURE

```
[ React Dashboard ]
        |
        v
[ API Gateway ]
        |
        +-------------------+
        |                   |
        v                   v
[ Auth Service ]     [ Gmail Connector Service ]
        |                   |
        v                   v
[ PostgreSQL DB ]    [ Gmail Sync Engine ]
                            |
                            v
                  [ Classification Pipeline ]
                            |
                            v
                      [ Applications DB ]
```

All services:
- Dockerized
- Isolated
- Communicate via HTTP
- Environment-based config only

## 2. AUTHENTICATION & ACCOUNT OWNERSHIP FLOW

### 2.1 Login
1. User clicks "Sign in with Google"
2. OAuth consent screen
3. Backend validates Google token
4. Backend issues its own JWT
5. Frontend stores ONLY backend JWT

### 2.2 Email Ownership Validation (MANDATORY)
Before syncing Gmail:
- Confirm: `Gmail emailAddress === authenticated user email`
- If mismatch → **BLOCK SYNC**

## 3. ACCOUNT SWITCH & PRIVACY ENFORCEMENT

### Trigger Conditions
- User logs out
- User logs in with different Google email
- User reconnects Gmail

### Mandatory Actions
Delete ALL stored:
- ✅ Emails
- ✅ Applications
- ✅ Gmail historyId
- ✅ Sync state
- ✅ Reset dashboard counters to zero
- ✅ Require fresh full sync

**❗ This is NOT optional**

## 4. GMAIL SYNC ENGINE (CRITICAL)

### 4.1 Initial Full Sync (First Login)
Algorithm (STRICT):
1. Use Gmail API `users.messages.list`
2. Paginate using `nextPageToken`
3. Loop until `nextPageToken == null`
4. Count every email fetched
5. Log: `Fetched: X emails (100%)`

❌ Hard limits like `maxResults=1200` are forbidden
❌ Early exits are forbidden

### 4.2 Incremental Sync (After First Sync)
1. Store Gmail `historyId`
2. On next sync:
   - Use `users.history.list`
   - Fetch only new/changed messages
   - Update counts
3. Never re-fetch entire mailbox unless account changed

## 5. TWO-STAGE CLASSIFICATION PIPELINE (MANDATORY)

### Stage 1 — High Recall (Loose Filter)
Goal: Do not miss job emails

Signals:
- Subject keywords
- Known ATS senders
- "Thank you for applying"
- "Interview"
- "Application update"

Result: `candidate_job_emails[]`

### Stage 2 — High Precision (Strict Classification)
Input: `candidate_job_emails[]`

Output: exactly ONE of:
- Applied
- Rejected
- Interview
- Offer / Accepted
- Ghosted

Rules:
- If uncertain → skip (but counted)
- Never assign multiple categories
- Never invent categories

## 6. GHOSTED DETECTION (TIME-BASED LOGIC)

Definition:
- Applied email exists
- No response after N days (configurable, e.g. 21 days)
- No rejection, interview, or offer after that

Process:
- Background job checks timestamps
- Moves application → Ghosted
- Dashboard updates automatically

## 7. COMPANY NAME EXTRACTION (ROBUST)

Multi-layer extraction:
1. Email domain (`@company.com`)
2. ATS branding (Greenhouse, Lever, Workday)
3. Signature parsing
4. Subject normalization
5. Fallback to sender name

Normalize:
- Remove "Careers", "Jobs", "Hiring"
- Merge duplicates

## 8. DATABASE MODEL

### User
- `id` (primary key)
- `email` (unique, indexed)
- `created_at`

### Application
- `id` (primary key)
- `user_id` (foreign key, CASCADE delete)
- `gmail_message_id` (unique, indexed)
- `company_name` (indexed)
- `role`
- `category` (indexed: applied, rejected, interview, offer, accepted, ghosted)
- `subject`
- `from_email`
- `received_at` (indexed)
- `last_updated`
- `snippet`

### SyncState
- `id` (primary key)
- `user_id` (unique, foreign key, CASCADE delete)
- `gmail_history_id` (indexed)
- `last_synced_at`
- `is_sync_running` (indexed)
- `sync_lock_expires_at` (indexed, TTL)
- `lock_job_id`

## 9. SYNC LOCKING (FIX "SYNC ALREADY RUNNING")

Rules:
- ✅ Use DB-based lock with TTL (e.g. 10 min)
- ✅ If lock expires → auto-release
- ✅ On crash → lock must clear
- ✅ No permanent lock allowed

## 10. LOGGING (STRICT REQUIREMENTS)

Logs MUST show:
```
Total emails in Gmail: 44,000
Fetched emails: 44,000
Job-related candidates: 1,050
Applied: 600
Rejected: 200
Interview: 50
Offer: 20
Ghosted: 180
Skipped: 42,950
```

Frontend must display SAME numbers.

## 11. DASHBOARD RULES (NO LIES)

- ✅ No pagination limits
- ✅ No frontend caps
- ✅ Real counts only
- ✅ Sync progress visible
- ✅ Errors visible in log panel

## 12. DOCKER-FIRST DEVELOPMENT SETUP

- ✅ `docker-compose` only
- ✅ Same commands on Mac & Windows
- ✅ `.env.example` committed
- ✅ No hardcoded ports
- ✅ One command to start everything

## 13. TEAM WORKFLOW

- ✅ Git branching
- ✅ Pre-commit checks
- ✅ Lint + tests in Docker
- ✅ Zero OS-specific scripts

---

**✅ THIS WORKFLOW IS FINAL AND AUTHORITATIVE**

Any deviation = bug. All code must strictly follow these rules.
