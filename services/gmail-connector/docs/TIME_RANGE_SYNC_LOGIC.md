# Perfect Time Range Sync Logic

## Overview

When user selects "Last 3/6/12/16 months", the system uses **STRICT time range enforcement** to sync ONLY emails from that exact time period.

## Date Calculation (PERFECT)

### Example: Last 3 Months
- **Today**: January 24, 2025, 12:30:45 UTC
- **Calculation**: `January 24, 2025 - 3 months = October 24, 2024`
- **Cutoff Date**: October 24, 2024, 00:00:00 UTC
- **Date Range**: October 24, 2024 to January 24, 2025
- **Gmail API Filter**: `after:1729728000` (Unix timestamp in seconds)

### How It Works
1. Uses `dateutil.relativedelta` for **exact month arithmetic** (not approximate days)
2. Handles month boundaries correctly:
   - Jan 31 - 1 month = Dec 31
   - Feb 28 - 1 month = Jan 28
   - Jan 24 - 3 months = Oct 24 (exact)
3. Sets cutoff to start of day (00:00:00 UTC) to include all emails from that day
4. Gmail API `after:` filter ensures ONLY emails with `internalDate >= cutoff` are fetched

## Flow Diagram

```
Frontend (User selects "Last 3 months")
  ↓
  { mode: "time_range", time_range_months: 3 }
  ↓
API Gateway (/api/gmail/sync)
  ↓
  Validates: time_range_months in [3, 6, 12, 16]
  Converts: { range: "3M" }
  ↓
Gmail Connector (/sync/start)
  ↓
  Validates: range in ["3M", "6M", "12M", "16M", "FULL"]
  Converts: mode="time_range", time_range_months=3
  Stores in checkpoint
  ↓
Worker (process_sync_job)
  ↓
  Reads checkpoint: mode="time_range", time_range_months=3
  Validates consistency
  ↓
Sync Engine (sync_all_emails)
  ↓
  Calculates EXACT cutoff date:
    now = Jan 24, 2025 12:30:45 UTC
    cutoff = now - relativedelta(months=3)
    cutoff = Oct 24, 2024 00:00:00 UTC
    timestamp_ms = 1729728000000
  ↓
Gmail Client (get_all_messages)
  ↓
  Gmail API query: q='after:1729728000'
  Returns ONLY emails with internalDate >= Oct 24, 2024 00:00:00 UTC
  ↓
Safety Check (in sync_engine)
  ↓
  Verifies all fetched messages have internalDate >= cutoff
  Logs warning if any messages are outside range
```

## Enforcement Points

### 1. Frontend Validation
- User must select one option: 3m, 6m, 12m, 16m, or full
- Sends: `{ mode: "time_range", time_range_months: 3 }`

### 2. API Gateway Validation
- Validates `time_range_months` is in [3, 6, 12, 16]
- If `time_range_months` provided → forces `mode="time_range"`
- Converts to `range: "3M"` format

### 3. Gmail Connector Validation
- Validates `range` is in ["3M", "6M", "12M", "16M", "FULL"]
- Converts to `mode="time_range"`, `time_range_months=3`
- Stores in checkpoint for worker

### 4. Worker Validation
- Reads checkpoint and validates consistency
- If `time_range_months` set → forces `mode="time_range"`
- Validates `time_range_months` is valid

### 5. Sync Engine Validation
- Calculates EXACT cutoff date using `relativedelta`
- Validates `time_range_months` is in [3, 6, 12, 16]
- Logs exact date range being synced

### 6. Gmail Client Enforcement
- Uses Gmail API `after:` filter when `start_timestamp_ms` is provided
- Query: `q='after:{timestamp_seconds}'`
- Gmail API returns ONLY emails with `internalDate >= timestamp`

### 7. Safety Check
- After fetching, verifies all messages have `internalDate >= cutoff`
- Logs warning if any messages are outside range (should never happen)

## Example Logs

When syncing "Last 3 months" on January 24, 2025:

```
═══════════════════════════════════════════════════════════════
TIME RANGE MODE: Last 3 months (STRICT ENFORCEMENT)
═══════════════════════════════════════════════════════════════
  Current date/time: 2025-01-24 12:30:45 UTC
  Cutoff date:       2024-10-24 00:00:00 UTC (emails AFTER this date)
  End date:          2025-01-24 23:59:59 UTC
  Date range:        2024-10-24 to 2025-01-24
  Gmail API filter:  after:1729728000 (Unix timestamp in seconds)
  Will sync ONLY emails with internalDate >= 2024-10-24 00:00:00 UTC
  Will NOT fetch any emails before 2024-10-24 00:00:00 UTC
═══════════════════════════════════════════════════════════════

TIME RANGE FILTER ACTIVE: 'after:1729728000' (2024-10-24 00:00:00 UTC)
  → Will ONLY fetch emails with internalDate >= 2024-10-24 00:00:00 UTC
  → Will NOT fetch any emails before this timestamp

SAFETY CHECK PASSED: All 500 messages are within time range
```

## Guarantees

✅ **Exact Date Calculation**: Uses proper month arithmetic, not approximate days  
✅ **Strict Enforcement**: Multiple validation points ensure time range is respected  
✅ **Gmail API Filter**: Uses `after:` filter to only fetch emails in range  
✅ **Safety Check**: Verifies fetched messages match time range  
✅ **No Fallback**: Never falls back to full history when time range is specified  
✅ **Clear Logging**: Shows exact date range being synced for verification
