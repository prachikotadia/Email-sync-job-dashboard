/**
 * Global feature flags – single source of truth.
 * (Named features.js for JS projects; use features.ts if using TypeScript.)
 *
 * 🚨 TEMPORARY GUEST MODE – REMOVE AFTER BACKEND STABILIZES
 * To disable: set GUEST_MODE_ENABLED = false. Guest mode disappears.
 * To remove fully: set false, delete src/mock/, remove guest logic from
 * AuthContext (isGuest, loginAsGuest, logoutGuest), Login (guest button),
 * Dashboard (mock imports, isGuest branches, badge, banner, chart, by-company),
 * GmailStatusCard (isGuest branch), Settings (logoutGuest). App still works.
 */
export const FEATURES = {
  GUEST_MODE_ENABLED: true, // TEMPORARY – set to false to remove guest mode
}
