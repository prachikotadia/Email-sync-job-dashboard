import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconRefresh, IconCheck, IconX, IconCalendar } from './icons'
import '../styles/SyncLogModal.css'

/**
 * SyncLogModal - Displays sync progress with explicit UX failure mode handling
 * 
 * FRONTEND FAILURE MODES (UX RULES):
 * 
 * 1. Sync paused:
 *    - Show "Sync paused" status message
 *    - Show last progress counts
 *    - Display reason if available
 * 
 * 2. Rate limited:
 *    - Show "Rate limit reached" warning
 *    - Display retry countdown (if available from event.errors[0].retry_after_seconds)
 *    - Show "Pausing and retrying..." message
 * 
 * 3. Backend restarted:
 *    - Auto-reconnect (handled by SSE hook)
 *    - Show "Reconnecting..." status
 *    - Resume progress display when reconnected
 * 
 * 4. Browser refreshed:
 *    - Fetch sync status from backend (stateless)
 *    - Reconnect to SSE stream
 *    - Resume progress display from last checkpoint
 *    - Show "Reconnecting to sync stream..." during reconnect
 */
export default function SyncLogModal({ progress, isRunning, onClose, onCancel, jobId, connected = true, reconnecting = false, sseError = null, syncStatus = null, selectedRange = null }) {
  const logContainerRef = useRef(null)
  const emailsListRef = useRef(null)
  const [userScrolledLogs, setUserScrolledLogs] = useState(false)
  const [userScrolledEmails, setUserScrolledEmails] = useState(false)

  // Prevent body scroll when modal is open
  useEffect(() => {
    const originalStyle = window.getComputedStyle(document.body).overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = originalStyle
    }
  }, [])

  // Auto-scroll logs to bottom unless user scrolled up
  useEffect(() => {
    if (logContainerRef.current && !userScrolledLogs) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [progress, userScrolledLogs])

  // Auto-scroll emails list to top (newest entries) unless user scrolled
  useEffect(() => {
    if (emailsListRef.current && !userScrolledEmails) {
      emailsListRef.current.scrollTop = 0
    }
  }, [progress, userScrolledEmails])

  // Reset scroll detection when new entries arrive (if user hasn't scrolled)
  const handleLogScroll = () => {
    const container = logContainerRef.current
    if (container) {
      const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 10
      if (isAtBottom) {
        setUserScrolledLogs(false)
      } else if (!userScrolledLogs) {
        setUserScrolledLogs(true)
      }
    }
  }

  const handleEmailsScroll = () => {
    const container = emailsListRef.current
    if (container) {
      const isAtTop = container.scrollTop <= 10
      if (isAtTop) {
        setUserScrolledEmails(false)
      } else if (!userScrolledEmails) {
        setUserScrolledEmails(true)
      }
    }
  }

  // Show modal if running or if there's progress data (even if completed)
  if (!isRunning && !progress) return null

  // Determine status from progress, lastEvent, or syncStatus (backwards compatible)
  const lastEvent = progress?.lastEvent || progress
  const status = lastEvent?.phase === 'done' ? 'completed' 
    : lastEvent?.phase === 'failed' ? 'failed'
    : lastEvent?.phase === 'canceled' ? 'canceled'
    : lastEvent?.phase === 'rate_limited' ? 'rate_limited'
    : lastEvent?.phase === 'paused' ? 'paused'
    : progress?.status || 'running'
  
  // Check for rate limit errors in event
  const rateLimitError = lastEvent?.errors?.find(err => err.code === 'RATE_LIMIT')
  const isRateLimited = status === 'rate_limited' || !!rateLimitError
  const retryAfterSeconds = rateLimitError?.retry_after_seconds
  
  const totalEmails = progress?.total_emails || progress?.total_scanned || 0
  const fetchedEmails = progress?.emails_fetched || progress?.total_fetched || 0
  const processedEmails = progress?.processed_emails || progress?.emails_fetched || fetchedEmails || 0
  const classified = progress?.counts || progress?.classified || {}
  const skipped = progress?.skipped || 0
  const applicationsFound = progress?.applications_found || 0
  
  // Use real email entries from backend
  const backendEmailEntries = progress?.email_entries || []
  
  // Calculate totals - use applications_found as primary source, fallback to sum of classified counts
  const totalStored = applicationsFound > 0 
    ? applicationsFound 
    : Object.values(classified).reduce((sum, val) => sum + (val || 0), 0)
  
  // Use real logs from backend + real-time events
  const backendLogs = progress?.logs || []
  
  // Extract real-time log from latest event if available
  const latestEvent = progress?.lastEvent || progress
  const realtimeLog = latestEvent?.log_message ? {
    time: latestEvent.ts ? new Date(latestEvent.ts) : new Date(),
    message: latestEvent.log_message,
    type: latestEvent.log_type || latestEvent.level || 'info',
    email_id: latestEvent.email_id,
    retry_count: latestEvent.retry_count,
    retry_after_seconds: latestEvent.retry_after_seconds
  } : null
  
  // Convert backend logs to display format (keep last 200)
  // Include email_id, retry_count, and retry_after_seconds from progressEvent logs
  const logEntries = backendLogs.slice(-200).map(log => ({
    time: log.time ? new Date(log.time) : new Date(),
    message: log.message || '',
    type: log.type || 'info',
    email_id: log.email_id,  // Include email_id for per-email tracking
    retry_count: log.retry_count,  // Include retry count
    retry_after_seconds: log.retry_after_seconds  // Include backoff duration
  }))
  
  // Add real-time log at the end if available and not already in logs
  if (realtimeLog && (!logEntries.length || logEntries[logEntries.length - 1].message !== realtimeLog.message)) {
    logEntries.push(realtimeLog)
  }

  // Format email entries for display - match image format: "Hire - [snippet] - [category]"
  const formatEmailEntry = (entry) => {
    const categoryMap = {
      'APPLIED': { label: 'Applied', status: 'success', color: '#16a34a' },
      'REJECTED': { label: 'Rejected', status: 'error', color: '#dc2626' },
      'INTERVIEW': { label: 'Interview', status: 'info', color: '#3b82f6' },
      'OFFER_ACCEPTED': { label: 'Accepted/Offer', status: 'success', color: '#16a34a' },
      'GHOSTED': { label: 'Ghosted', status: 'warning', color: '#f59e0b' },
    }
    
    const categoryInfo = categoryMap[entry.category] || { 
      label: entry.category || 'Other', 
      status: 'info',
      color: '#64748b'
    }
    
    // Format as "Hire - [snippet] - [category]" to match image
    const snippet = entry.snippet || entry.subject || 'No description'
    const fullText = `Hire - ${snippet} - ${categoryInfo.label}`
    
    return {
      id: entry.id || Math.random(),
      fullText,
      snippet,
      category: categoryInfo.label,
      status: categoryInfo.status,
      color: categoryInfo.color
    }
  }

  const emailEntries = backendEmailEntries.map(formatEmailEntry)

  const formatTime = (date) => {
    const dateObj = date instanceof Date ? date : new Date(date)
    return dateObj.toLocaleTimeString('en-US', {
      hour12: true,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  // Determine status display (with failure mode handling)
  const statusTitle = status === 'completed' ? 'Complete' 
    : status === 'failed' ? 'Failed'
    : status === 'canceled' ? 'Canceled'
    : status === 'rate_limited' ? 'Rate Limited'
    : status === 'paused' ? 'Paused'
    : 'Syncing...'
  const showSummaryBox = true  // Always show summary for all states
  
  // Calculate progress percentage for progress bar
  // Use processed_emails vs total_emails for accurate progress
  const progressPercentage = totalEmails > 0 
    ? Math.min(100, Math.round((processedEmails / totalEmails) * 100))
    : processedEmails > 0 
    ? Math.min(50, Math.round((processedEmails / 100) * 50)) // Show partial progress if total unknown
    : 0

  const modalContent = (
    <div className="sync-log-modal-overlay" onClick={onClose}>
      <div className="sync-log-modal neo-card" onClick={(e) => e.stopPropagation()}>
        {/* Header with status */}
        <div className="sync-log-modal-header-new">
          <div className="sync-log-status-header">
            {status === 'completed' && (
              <div className="sync-log-status-icon-circle sync-log-icon-success-circle">
                <IconCheck className="sync-log-status-icon" />
              </div>
            )}
            {status === 'running' && <IconRefresh className="sync-log-status-icon sync-log-spinning" />}
            {status === 'failed' && (
              <div className="sync-log-status-icon-circle sync-log-icon-error-circle">
                <IconX className="sync-log-status-icon" />
              </div>
            )}
            {status === 'canceled' && (
              <div className="sync-log-status-icon-circle sync-log-icon-error-circle">
                <IconX className="sync-log-status-icon" />
              </div>
            )}
            <div className="sync-log-status-text">
              <h2 className={status === 'completed' ? 'sync-log-complete' : status === 'failed' ? 'sync-log-failed' : ''}>
                {statusTitle}
              </h2>
              {/* FAILURE MODE MESSAGES - Explicit UX rules */}
              {status === 'rate_limited' && (
                <p className="sync-log-subtitle" style={{ color: '#f59e0b' }}>
                  Rate limit reached. Pausing sync and retrying...
                  {retryAfterSeconds && ` (Retrying in ${retryAfterSeconds}s)`}
                </p>
              )}
              {status === 'paused' && (
                <p className="sync-log-subtitle" style={{ color: '#f59e0b' }}>
                  Sync is paused. Will resume automatically.
                </p>
              )}
              {reconnecting && (
                <p className="sync-log-subtitle" style={{ color: '#f59e0b' }}>
                  Backend restarted or connection lost. Reconnecting to sync stream...
                </p>
              )}
              {!connected && !reconnecting && sseError && (
                <p className="sync-log-subtitle" style={{ color: '#dc2626' }}>
                  Connection lost: {sseError}. Attempting to reconnect...
                </p>
              )}
              {connected && !reconnecting && status === 'running' && !isRateLimited && status !== 'paused' && (
                <p className="sync-log-subtitle">Please wait while we sync your data.</p>
              )}
              {status === 'completed' && (
                <p className="sync-log-subtitle">Sync completed successfully!</p>
              )}
              {status === 'failed' && (
                <p className="sync-log-subtitle">Sync encountered an error. Please try again.</p>
              )}
              {status === 'canceled' && (
                <p className="sync-log-subtitle">Sync was canceled by user.</p>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {isRunning && status !== 'canceled' && onCancel && jobId && (
              <button
                className="sync-log-cancel-btn"
                onClick={onCancel}
                disabled={status === 'canceled'}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#dc2626',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                Cancel Sync
              </button>
            )}
            <button className="sync-log-modal-close" onClick={onClose} aria-label="Close">
              <IconX />
            </button>
          </div>
        </div>

        {/* Status Summary Box - Always visible with progress (all failure modes) */}
        <div className={`sync-log-summary-box ${
          status === 'failed' ? 'sync-log-summary-error' : 
          status === 'rate_limited' || status === 'paused' ? 'sync-log-summary-warning' : 
          ''
        }`}>
          {status === 'completed' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>✓</span>
              <span>{totalStored.toLocaleString()} emails stored successfully</span>
            </div>
          ) : status === 'failed' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>✗</span>
              <span>Sync failed. Please try again.</span>
            </div>
          ) : status === 'rate_limited' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span>⚠</span>
              <span>
                Rate limit reached. Sync paused temporarily.
                {retryAfterSeconds && ` Retrying in ${retryAfterSeconds} seconds...`}
              </span>
            </div>
          ) : status === 'paused' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>⏸</span>
              <span>Sync is paused. Will resume automatically.</span>
            </div>
          ) : (
            <div className="sync-log-progress-info">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600 }}>Status: {statusTitle}</span>
                {totalEmails > 0 && (
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    {processedEmails} / {totalEmails} emails
                  </span>
                )}
              </div>
              {totalEmails > 0 && (
                <div className="sync-log-progress-bar-container">
                  <div className="sync-log-progress-bar">
                    <div 
                      className="sync-log-progress-bar-fill" 
                      style={{ width: `${progressPercentage}%` }}
                    />
                  </div>
                  <div className="sync-log-progress-text">
                    Progress: {progressPercentage}% complete
                  </div>
                </div>
              )}
              {totalEmails === 0 && processedEmails === 0 && (
                <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                  Initializing sync process...
                </div>
              )}
            </div>
          )}
        </div>

        {/* Real-Time Logs Section - Always Visible */}
        <div className="sync-log-detailed-logs">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4>Real-Time Sync Logs</h4>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {selectedRange && (
                <div className="sync-log-range-badge">
                  <IconCalendar style={{ width: '14px', height: '14px', marginRight: '4px' }} />
                  {selectedRange.label}
                </div>
              )}
            </div>
          </div>
          <div 
            className="sync-log-container" 
            ref={logContainerRef}
            onScroll={handleLogScroll}
          >
            {logEntries.length === 0 ? (
              <div className="sync-log-entry sync-log-info">
                <span className="sync-log-time">[{formatTime(new Date())}]</span>
                <span className="sync-log-message">Initializing sync...</span>
              </div>
            ) : (
              logEntries.map((entry, index) => {
                // Determine icon/emoji based on log type and message content
                let icon = ''
                if (entry.type === 'success') {
                  icon = '✓'
                } else if (entry.type === 'error' || entry.type === 'warning') {
                  icon = '⚠'
                } else if (entry.message.includes('Scanning') || entry.message.includes('📋')) {
                  icon = '📋'
                } else if (entry.message.includes('Fetching') || entry.message.includes('📥')) {
                  icon = '📥'
                } else if (entry.message.includes('Classifying') || entry.message.includes('🤖')) {
                  icon = '🤖'
                } else if (entry.message.includes('Saving') || entry.message.includes('💾')) {
                  icon = '💾'
                } else {
                  icon = '•'
                }
                
                return (
                  <div key={index} className={`sync-log-entry sync-log-${entry.type || 'info'}`}>
                    <span className="sync-log-time">[{formatTime(entry.time)}]</span>
                    <span className="sync-log-icon">{icon}</span>
                    <span className="sync-log-message">
                      {entry.message}
                      {entry.retry_count && entry.retry_count > 0 && (
                        <span className="sync-log-retry-info" title={`Retry attempt ${entry.retry_count}`}>
                          {' '}(Retry {entry.retry_count})
                        </span>
                      )}
                      {entry.retry_after_seconds && (
                        <span className="sync-log-retry-info" title={`Retrying in ${entry.retry_after_seconds}s`}>
                          {' '}(Retry in {Math.round(entry.retry_after_seconds)}s)
                        </span>
                      )}
                    </span>
                    {entry.email_id && (
                      <span className="sync-log-email-id" title={`Gmail Message ID: ${entry.email_id}`}>
                        {entry.email_id.substring(0, 8)}...
                      </span>
                    )}
                  </div>
                )
              })
            )}
            {status === 'running' && (
              <div className="sync-log-entry sync-log-info">
                <span className="sync-log-time">[{formatTime(new Date())}]</span>
                <span className="sync-log-message">Processing... <span className="sync-log-dots">...</span></span>
              </div>
            )}
          </div>
        </div>

        {/* Progress Section - Email List */}
        {(status === 'running' || status === 'completed') && (
          <div className="sync-log-progress-section">
            <h3 className="sync-log-progress-title">
              EMAILS BEING ADDED ({Math.max(processedEmails, emailEntries.length)} OF {totalStored || totalEmails || '...'})
            </h3>
            
            {/* Individual Email Entries - Scrollable List */}
            <div 
              className="sync-log-emails-list" 
              ref={emailsListRef}
              onScroll={handleEmailsScroll}
            >
              {emailEntries.length > 0 ? (
                emailEntries.map((entry, index) => (
                  <div key={entry.id || index} className="sync-log-email-entry">
                    <div 
                      className="sync-log-email-dot" 
                      style={{ backgroundColor: entry.color || '#16a34a' }}
                    />
                    <div className="sync-log-email-content">
                      <div className="sync-log-email-text">{entry.fullText}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="sync-log-email-entry sync-log-processing">
                  <div className="sync-log-email-dot sync-log-dot-info" />
                  <div className="sync-log-email-content">
                    <div className="sync-log-email-text">Processing emails...</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="sync-log-modal-actions">
          <button 
            type="button" 
            className={`sync-log-modal-btn ${status === 'completed' || status === 'failed' ? 'sync-log-modal-btn-close' : 'sync-log-modal-btn-secondary'}`} 
            onClick={onClose}
          >
            {status === 'running' ? 'Minimize' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}