# JobPulse AI - Requirements Checklist

## ✅ NON-NEGOTIABLE RULES (Enforced in Code)

### ❌ NO email data persists across account switch
- **Location**: `services/gmail-connector/app/state.py` - `clear_user_state()` method
- **Location**: `services/api-gateway/app/routers/auth.py` - `logout()` endpoint calls `/clear`
- **Location**: `frontend/src/services/authService.js` - `logout()` clears all frontend state
- **Enforcement**: Every logout/account switch triggers data clearing in both frontend and backend

### ❌ NO frontend pagination limits (50, 100, etc.)
- **Location**: `frontend/src/services/gmailService.js` - `getApplications()` has NO page/limit parameters
- **Location**: `frontend/src/pages/Dashboard.jsx` - Uses all applications, no pagination
- **Enforcement**: Backend returns ALL applications, frontend renders all using virtualization-ready structure

### ❌ NO sync skipping unless explicitly locked
- **Location**: `services/gmail-connector/app/main.py` - `start_sync()` checks for locks
- **Location**: `services/gmail-connector/app/state.py` - Lock management
- **Enforcement**: Sync only skips if lock exists, locks released on service restart

### ❌ NO silent failures
- **Location**: `frontend/src/services/apiClient.js` - Global error interceptor
- **Location**: All API calls have try/catch with visible error banners
- **Enforcement**: All errors are logged and displayed to user

### ✅ Docker is the ONLY execution environment
- **Location**: All services have Dockerfiles
- **Location**: `docker-compose.yml` orchestrates everything
- **Enforcement**: No local dependencies required

### ✅ Every login = fresh sync
- **Location**: `services/gmail-connector/app/sync_engine.py` - `sync_all_emails()` clears state first
- **Enforcement**: `clear_user_state()` called at start of every sync

### ✅ Gmail total fetched count must match Gmail API reality
- **Location**: `services/gmail-connector/app/gmail_client.py` - `get_all_messages()` fetches ALL
- **Location**: `services/gmail-connector/app/sync_engine.py` - Counts match actual fetched messages
- **Enforcement**: No estimation, only real counts from API

### ✅ Dashboard numbers must be REAL, not estimated
- **Location**: `services/gmail-connector/app/main.py` - `calculate_stats()` uses actual application data
- **Location**: `frontend/src/components/StatsOverview.jsx` - Displays backend counts directly
- **Enforcement**: Stats calculated from actual applications, never estimated

## 🎯 FRONTEND REQUIREMENTS

### 1. AUTH ✅
- ✅ Uses backend JWT only (`frontend/src/services/authService.js`)
- ✅ Never stores Google tokens in frontend
- ✅ On logout: clears all frontend state AND forces backend to delete cached data

### 2. SYNC UI ✅
- ✅ Shows total emails scanned (`frontend/src/components/SyncProgress.jsx`)
- ✅ Shows total emails fetched
- ✅ Shows classified counts (Applied, Rejected, Interview, Offer, Accepted, Ghosted)
- ✅ Values come from backend response, never computed in frontend

### 3. SYNC PROGRESS ✅
- ✅ Implements polling (`frontend/src/pages/Dashboard.jsx` - `startProgressPolling()`)
- ✅ Shows live counter incrementing
- ✅ Disables sync button when running
- ✅ Shows lock reason if locked

### 4. DASHBOARD ✅
- ✅ NO frontend filtering limits
- ✅ NO default page size
- ✅ Structure ready for virtualization (react-window compatible)
- ✅ Displays warning if backend returns partial data

### 5. ERROR HANDLING ✅
- ✅ 4xx/5xx responses show visible error banner
- ✅ Logs exact backend message
- ✅ Never swallows errors

### 6. CROSS-PLATFORM ✅
- ✅ No OS-specific paths
- ✅ No filesystem access
- ✅ Docker-only assumptions

### 7. STATE MANAGEMENT ✅
- ✅ Single source of truth (AuthContext)
- ✅ Never duplicates auth or sync state
- ✅ React strict mode safe (uses refs to prevent double execution)

## 🧪 ACCEPTANCE CHECKLIST

Before deployment, verify:

- ✅ Login works on Mac & Windows
- ✅ Gmail status shows 503 ONLY if service is down
- ✅ Sync button unlocks after crash/restart
- ✅ Dashboard shows exact Gmail count
- ✅ Account switch clears all previous data
- ✅ No 50 emails anywhere in UI or API

## 🚨 FIXED ISSUES

The following issues have been eliminated:

1. ✅ **Frontend hard limits** - Removed all pagination limits
2. ✅ **Backend pagination defaults** - Backend returns ALL emails
3. ✅ **Sync locks never released** - Locks cleared on service restart
4. ✅ **React double-effect execution** - Protected with refs
5. ✅ **Docker volumes not reset on account switch** - Clear endpoint implemented
