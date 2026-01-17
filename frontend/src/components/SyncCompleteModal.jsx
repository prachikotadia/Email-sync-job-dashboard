import { IconCheck } from './icons'
import '../styles/SyncCompleteModal.css'

export default function SyncCompleteModal({ progress, onClose, onViewLogs }) {
  if (!progress) return null

  const totalStored = progress.totalFetched ?? progress.totalScanned ?? 0
  const classified = progress.classified || {}
  const applications = progress.applications || []
  const displayList = applications.slice(0, 15)

  const logParts = []
  if (Object.keys(classified).length > 0) {
    const parts = Object.entries(classified)
      .map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`)
      .join(', ')
    logParts.push(`Sync completed! Stored ${totalStored} job application emails (${parts}).`)
  } else {
    logParts.push(`Sync completed! Stored ${totalStored} job application emails.`)
  }
  logParts.push(`Created/updated ${applications.length || totalStored} applications.`)

  const now = new Date()
  const timeStr = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <div className="sync-modal-overlay" onClick={onClose}>
      <div className="sync-modal neo-card" onClick={(e) => e.stopPropagation()}>
        <div className="sync-modal-header">
          <div className="sync-modal-success">
            <div className="sync-modal-check">
              <IconCheck />
            </div>
            <span className="sync-modal-complete">Complete</span>
          </div>
          <p className="sync-modal-sub">Please wait while we sync your data.</p>
        </div>

        <div className="sync-modal-stored neo-card-inset">
          <IconCheck />
          <span>{totalStored.toLocaleString()} emails stored</span>
        </div>

        <div className="sync-modal-section">
          <h4>EMAILS BEING ADDED ({displayList.length} OF {totalStored})</h4>
          <div className="sync-modal-list">
            {displayList.length === 0 ? (
              <p className="sync-modal-list-empty">No entries to display.</p>
            ) : (
              displayList.map((app, i) => (
                <div key={app.id || i} className="sync-modal-list-item">
                  <div>
                    <span className="sync-modal-list-company">{app.company || 'Unknown'}</span>
                    <span className="sync-modal-list-desc">
                      {app.role || ''} – {app.status || 'Processed'}
                    </span>
                  </div>
                  <span className="sync-modal-list-dot" />
                </div>
              ))
            )}
          </div>
          <div className="sync-modal-log">
            <div className="sync-modal-log-entry">[{timeStr}] Updating sync timestamp...</div>
            <div className="sync-modal-log-entry">[{timeStr}] {logParts.join(' ')}</div>
          </div>
        </div>

        <div className="sync-modal-actions">
          <button type="button" className="sync-modal-btn sync-modal-btn-primary" onClick={onViewLogs || onClose}>
            &gt; View Full Logs
          </button>
          <button type="button" className="sync-modal-btn sync-modal-btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
