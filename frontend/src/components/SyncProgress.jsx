import '../styles/SyncProgress.css'

function SyncProgress({ progress }) {
  if (!progress) {
    return (
      <div className="sync-progress">
        <p>Initializing sync...</p>
      </div>
    )
  }

  const {
    status,
    totalScanned = 0,
    totalFetched = 0,
    classified = {},
  } = progress

  return (
    <div className="sync-progress">
      <h3>Sync Progress</h3>
      
      <div className="progress-stats">
        <div className="stat-item">
          <label>Status</label>
          <span className={`status-badge status-${status}`}>{status}</span>
        </div>
        
        <div className="stat-item">
          <label>Emails Scanned</label>
          <span className="stat-value">{totalScanned.toLocaleString()}</span>
        </div>
        
        <div className="stat-item">
          <label>Emails Fetched</label>
          <span className="stat-value">{totalFetched.toLocaleString()}</span>
        </div>
      </div>

      {Object.keys(classified).length > 0 && (
        <div className="classified-counts">
          <h4>Classified</h4>
          <div className="counts-grid">
            {Object.entries(classified).map(([status, count]) => (
              <div key={status} className="count-item">
                <span className="count-label">{status}</span>
                <span className="count-value">{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {status === 'completed' && (
        <div className="sync-complete">
          ✓ Sync completed successfully
        </div>
      )}

      {status === 'failed' && (
        <div className="sync-error">
          ✗ Sync failed. Please try again.
        </div>
      )}
    </div>
  )
}

export default SyncProgress
