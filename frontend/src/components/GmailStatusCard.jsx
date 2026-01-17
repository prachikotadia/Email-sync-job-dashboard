import '../styles/GmailStatusCard.css'

function GmailStatusCard({ status, onSync, isSyncing, isGuest }) {
  // 🚨 TEMPORARY GUEST MODE – Gmail sync disabled, no API calls
  if (isGuest) {
    return (
      <div className="gmail-status-card">
        <div className="status-header">
          <h2>Gmail Connection</h2>
        </div>
        <div className="status-content">
          <div className="gmail-guest-message">
            Gmail sync is disabled in Guest Mode.
          </div>
        </div>
      </div>
    )
  }

  const isConnected = status?.connected === true
  const lockReason = status?.lockReason

  return (
    <div className="gmail-status-card">
      <div className="status-header">
        <h2>Gmail Connection</h2>
        <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      <div className="status-content">
        {status?.error === 'Service unavailable' ? (
          <div className="error-message">
            Gmail service is currently unavailable (503). Please try again later.
          </div>
        ) : !isConnected ? (
          <div className="info-message">
            Connect your Gmail account to start tracking applications.
          </div>
        ) : (
          <div className="info-message">
            Gmail account connected and ready to sync.
          </div>
        )}

        {lockReason && (
          <div className="lock-message">
            Sync locked: {lockReason}
          </div>
        )}

        <button
          onClick={onSync}
          disabled={isSyncing || !isConnected || !!lockReason}
          className="sync-button"
        >
          {isSyncing ? 'Syncing...' : 'Start Sync'}
        </button>
      </div>
    </div>
  )
}

export default GmailStatusCard
