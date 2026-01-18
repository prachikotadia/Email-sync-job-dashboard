import { useEffect, useRef } from 'react'
import { IconRefresh, IconCheck, IconX } from './icons'
import '../styles/SyncLogModal.css'

export default function SyncLogModal({ progress, isRunning, onClose }) {
  const logContainerRef = useRef(null)

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [progress])

  if (!isRunning && !progress) return null

  const status = progress?.status || 'running'
  const totalEmails = progress?.total_emails || progress?.total_scanned || 0
  const fetchedEmails = progress?.fetched_emails || progress?.total_fetched || 0
  const classified = progress?.classified || {}
  const skipped = progress?.skipped || 0

  // Generate log entries
  const logEntries = []
  
  if (status === 'running') {
    logEntries.push({
      time: new Date(),
      message: 'Starting Gmail sync...',
      type: 'info'
    })
    
    if (totalEmails > 0) {
      logEntries.push({
        time: new Date(),
        message: `Scanning Gmail: Found ${totalEmails.toLocaleString()} total emails`,
        type: 'info'
      })
    }
    
    if (fetchedEmails > 0) {
      logEntries.push({
        time: new Date(),
        message: `Fetched ${fetchedEmails.toLocaleString()} emails for processing`,
        type: 'info'
      })
    }
    
    const candidateCount = Object.values(classified).reduce((sum, val) => sum + (val || 0), 0)
    if (candidateCount > 0) {
      logEntries.push({
        time: new Date(),
        message: `Identified ${candidateCount.toLocaleString()} job-related emails`,
        type: 'info'
      })
    }
    
    if (classified.applied > 0) {
      logEntries.push({
        time: new Date(),
        message: `✓ Classified ${classified.applied.toLocaleString()} as Applied`,
        type: 'success'
      })
    }
    
    if (classified.rejected > 0) {
      logEntries.push({
        time: new Date(),
        message: `✓ Classified ${classified.rejected.toLocaleString()} as Rejected`,
        type: 'success'
      })
    }
    
    if (classified.interview > 0) {
      logEntries.push({
        time: new Date(),
        message: `✓ Classified ${classified.interview.toLocaleString()} as Interview`,
        type: 'success'
      })
    }
    
    if (classified.offer > 0) {
      logEntries.push({
        time: new Date(),
        message: `✓ Classified ${classified.offer.toLocaleString()} as Offer / Accepted`,
        type: 'success'
      })
    }
    
    if (classified.ghosted > 0) {
      logEntries.push({
        time: new Date(),
        message: `✓ Classified ${classified.ghosted.toLocaleString()} as Ghosted`,
        type: 'success'
      })
    }
    
    if (skipped > 0) {
      logEntries.push({
        time: new Date(),
        message: `Skipped ${skipped.toLocaleString()} emails (not job applications)`,
        type: 'warning'
      })
    }
  } else if (status === 'completed') {
    logEntries.push({
      time: new Date(),
      message: '✓ Sync completed successfully!',
      type: 'success'
    })
    logEntries.push({
      time: new Date(),
      message: `Total: ${fetchedEmails.toLocaleString()} emails processed, ${Object.values(classified).reduce((sum, val) => sum + (val || 0), 0).toLocaleString()} applications created`,
      type: 'success'
    })
  } else if (status === 'failed') {
    logEntries.push({
      time: new Date(),
      message: '✗ Sync failed. Please try again.',
      type: 'error'
    })
  }

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <div className="sync-log-modal-overlay" onClick={onClose}>
      <div className="sync-log-modal neo-card" onClick={(e) => e.stopPropagation()}>
        <div className="sync-log-modal-header">
          <div className="sync-log-modal-title">
            {status === 'running' && <IconRefresh className="sync-log-spinning" />}
            {status === 'completed' && <IconCheck className="sync-log-success" />}
            {status === 'failed' && <IconX className="sync-log-error" />}
            <h3>Gmail Sync {status === 'running' ? 'In Progress' : status === 'completed' ? 'Complete' : 'Failed'}</h3>
          </div>
          <button className="sync-log-modal-close" onClick={onClose} aria-label="Close">
            <IconX />
          </button>
        </div>

        <div className="sync-log-modal-stats">
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Total Emails</span>
            <span className="sync-log-stat-value">{totalEmails.toLocaleString()}</span>
          </div>
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Fetched</span>
            <span className="sync-log-stat-value">{fetchedEmails.toLocaleString()}</span>
          </div>
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Applied</span>
            <span className="sync-log-stat-value">{classified.applied || 0}</span>
          </div>
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Rejected</span>
            <span className="sync-log-stat-value">{classified.rejected || 0}</span>
          </div>
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Interview</span>
            <span className="sync-log-stat-value">{classified.interview || 0}</span>
          </div>
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Offer</span>
            <span className="sync-log-stat-value">{classified.offer || 0}</span>
          </div>
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Ghosted</span>
            <span className="sync-log-stat-value">{classified.ghosted || 0}</span>
          </div>
          <div className="sync-log-stat">
            <span className="sync-log-stat-label">Skipped</span>
            <span className="sync-log-stat-value">{skipped.toLocaleString()}</span>
          </div>
        </div>

        <div className="sync-log-modal-content">
          <h4>Sync Logs</h4>
          <div className="sync-log-container" ref={logContainerRef}>
            {logEntries.length === 0 ? (
              <div className="sync-log-entry">
                <span className="sync-log-time">[{formatTime(new Date())}]</span>
                <span className="sync-log-message">Initializing sync...</span>
              </div>
            ) : (
              logEntries.map((entry, index) => (
                <div key={index} className={`sync-log-entry sync-log-${entry.type}`}>
                  <span className="sync-log-time">[{formatTime(entry.time)}]</span>
                  <span className="sync-log-message">{entry.message}</span>
                </div>
              ))
            )}
            {status === 'running' && (
              <div className="sync-log-entry sync-log-info">
                <span className="sync-log-time">[{formatTime(new Date())}]</span>
                <span className="sync-log-message">Processing... <span className="sync-log-dots">...</span></span>
              </div>
            )}
          </div>
        </div>

        <div className="sync-log-modal-actions">
          {status === 'completed' || status === 'failed' ? (
            <button type="button" className="sync-log-modal-btn sync-log-modal-btn-primary" onClick={onClose}>
              Close
            </button>
          ) : (
            <button type="button" className="sync-log-modal-btn sync-log-modal-btn-secondary" onClick={onClose}>
              Close (Sync continues in background)
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
