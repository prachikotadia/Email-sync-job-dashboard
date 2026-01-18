import { useEffect, useRef, useState } from 'react'
import { gmailService } from '../services/gmailService'
import { IconRefresh, IconCheck, IconX, IconAlertCircle } from './icons'
import '../styles/SyncDialog.css'

export default function SyncDialog({ jobId, isOpen, onClose, onComplete }) {
  const [progress, setProgress] = useState(null)
  const [logs, setLogs] = useState([])
  const [lastLogSeq, setLastLogSeq] = useState(0)
  const [autoScroll, setAutoScroll] = useState(true)
  const logContainerRef = useRef(null)
  const pollIntervalRef = useRef(null)
  const logPollIntervalRef = useRef(null)

  // Poll progress every 2 seconds
  useEffect(() => {
    if (!isOpen || !jobId) {
      // Clear intervals when modal closes
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      if (logPollIntervalRef.current) {
        clearInterval(logPollIntervalRef.current)
        logPollIntervalRef.current = null
      }
      return
    }

    const pollProgress = async () => {
      try {
        const data = await gmailService.getSyncProgress(jobId)
        setProgress(data)
        
        // If completed or failed, stop progress polling but KEEP log polling active
        // This ensures all final logs are captured and displayed
        if (data.state === 'COMPLETED' || data.state === 'FAILED' || data.state === 'CANCELLED') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
          // DO NOT stop log polling - continue to fetch any remaining logs
          // Log polling will continue until user closes dialog
          // Don't call onComplete automatically - let user see results
          // onComplete will be called when user clicks "View Dashboard"
        }
      } catch (error) {
        console.error('Failed to poll progress:', error)
      }
    }

    pollProgress() // Initial poll
    pollIntervalRef.current = setInterval(pollProgress, 50) // Poll every 50ms for ultra-real-time updates

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [isOpen, jobId, onComplete])

  // Poll logs every 1 second - continue even after completion
  useEffect(() => {
    if (!isOpen || !jobId) {
      // Clear interval when modal closes
      if (logPollIntervalRef.current) {
        clearInterval(logPollIntervalRef.current)
        logPollIntervalRef.current = null
      }
      return
    }

    const pollLogs = async () => {
      try {
        const data = await gmailService.getSyncLogs(jobId, lastLogSeq)
        if (data.logs && data.logs.length > 0) {
          console.log(`📝 Received ${data.logs.length} new log entries`)
          setLogs(prev => {
            // Avoid duplicates by checking seq
            const existingSeqs = new Set(prev.map(log => log.seq))
            const newLogs = data.logs.filter(log => !existingSeqs.has(log.seq))
            return [...prev, ...newLogs]
          })
          setLastLogSeq(data.lastSeq)
        }
      } catch (error) {
        console.error('Failed to poll logs:', error)
        // Don't stop polling on error - might be transient
      }
    }

    pollLogs() // Initial poll
    logPollIntervalRef.current = setInterval(pollLogs, 50) // Poll every 50ms for ultra-real-time log updates

    return () => {
      if (logPollIntervalRef.current) {
        clearInterval(logPollIntervalRef.current)
        logPollIntervalRef.current = null
      }
    }
  }, [isOpen, jobId, lastLogSeq])

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const formatTime = (seconds) => {
    if (!seconds) return 'Calculating...'
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
  }

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  if (!isOpen) {
    return null
  }

  // Determine state
  const isStarting = !jobId || !progress
  const isComplete = progress?.state === 'COMPLETED'
  const isFailed = progress?.state === 'FAILED'
  const isRunning = progress?.state === 'RUNNING' || progress?.state === 'QUEUED'

  return (
    <div 
      className="sync-dialog-overlay" 
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 2147483647, // Maximum z-index value
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)'
      }}
    >
      <div 
        className="sync-dialog" 
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'relative',
          zIndex: 2147483647, // Maximum z-index value
          pointerEvents: 'auto'
        }}
      >
        {/* Header */}
        <div className="sync-dialog-header">
          <div className="sync-dialog-title">
            {isStarting && <IconRefresh className="sync-dialog-spinner" />}
            {isRunning && <IconRefresh className="sync-dialog-spinner" />}
            {isComplete && <IconCheck className="sync-dialog-success" />}
            {isFailed && <IconAlertCircle className="sync-dialog-error" />}
            <h2>
              {isStarting && 'Starting Gmail Sync...'}
              {isRunning && 'Syncing Your Gmail...'}
              {isComplete && 'Sync Complete!'}
              {isFailed && 'Sync Failed'}
            </h2>
          </div>
          <button className="sync-dialog-close" onClick={onClose} aria-label="Close">
            <IconX />
          </button>
        </div>

        {/* Subtitle */}
        <p className="sync-dialog-subtitle">
          {isStarting && 'Initializing sync process...'}
          {isRunning && 'Please wait while we sync your emails.'}
          {isComplete && `Sync completed successfully! Found ${(progress?.applicationsCreatedOrUpdated || 0).toLocaleString()} job applications.`}
          {isFailed && progress?.errorMessage}
        </p>

        {/* Progress Bar - Show for running, starting, and completed states */}
        {(isRunning || isStarting || isComplete) && (
          <div className="sync-dialog-progress-bar-container">
            <div className="sync-dialog-progress-bar">
              <div
                className="sync-dialog-progress-fill"
                style={{ 
                  width: `${Math.min(progress?.percent || (isComplete ? 100 : 0), 100)}%`,
                  backgroundColor: isComplete ? '#16a34a' : undefined
                }}
              />
            </div>
            <div className="sync-dialog-progress-text">
              {isComplete 
                ? `Completed: ${(progress?.emailsFetched || 0).toLocaleString()} / ${(progress?.totalEmailsEstimated || progress?.emailsFetched || 0).toLocaleString()} emails processed`
                : progress?.totalEmailsEstimated
                  ? `Processing: ${(progress.emailsFetched || 0).toLocaleString()} / ${progress.totalEmailsEstimated.toLocaleString()} emails`
                  : 'Initializing...'}
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="sync-dialog-stats">
          <div className="sync-dialog-stat">
            <span className="stat-label">Total Emails</span>
            <span className="stat-value">{progress?.totalEmailsEstimated?.toLocaleString() || '—'}</span>
          </div>
          <div className="sync-dialog-stat">
            <span className="stat-label">Fetched</span>
            <span className="stat-value">{(progress?.emailsFetched || 0).toLocaleString()}</span>
          </div>
          <div className="sync-dialog-stat">
            <span className="stat-label">Classified</span>
            <span className="stat-value">{(progress?.emailsClassified || 0).toLocaleString()}</span>
          </div>
          <div className="sync-dialog-stat">
            <span className="stat-label">Stored</span>
            <span className="stat-value">{(progress?.applicationsCreatedOrUpdated || 0).toLocaleString()}</span>
          </div>
          <div className="sync-dialog-stat">
            <span className="stat-label">Skipped</span>
            <span className="stat-value">{(progress?.skipped || 0).toLocaleString()}</span>
          </div>
          {(isRunning || isStarting) && progress?.etaSeconds && (
            <div className="sync-dialog-stat">
              <span className="stat-label">ETA</span>
              <span className="stat-value">{formatTime(progress.etaSeconds)}</span>
            </div>
          )}
        </div>

        {/* Category Breakdown */}
        {progress?.categoryCounts && Object.keys(progress.categoryCounts).length > 0 && (
          <div className="sync-dialog-categories">
            <h4>Applications by Category</h4>
            <div className="sync-dialog-category-badges">
              {Object.entries(progress.categoryCounts).map(([category, count]) => (
                <span key={category} className="category-badge">
                  {category.charAt(0).toUpperCase() + category.slice(1)}: {count}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Logs Section */}
        <div className="sync-dialog-logs-section">
          <div className="sync-dialog-logs-header">
            <h4>Sync Logs</h4>
            <label className="auto-scroll-toggle">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              Auto-scroll
            </label>
          </div>
          <div
            className="sync-dialog-logs"
            ref={logContainerRef}
            onScroll={() => {
              if (logContainerRef.current) {
                const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current
                if (scrollTop + clientHeight < scrollHeight - 50) {
                  setAutoScroll(false)
                }
              }
            }}
          >
            {logs.length === 0 ? (
              <div className="log-entry">
                {isStarting ? 'Initializing sync...' : 'Waiting for logs...'}
                {jobId && <span style={{ marginLeft: '10px', color: '#6b7280', fontSize: '0.8rem' }}>(Job ID: {jobId.substring(0, 8)}...)</span>}
              </div>
            ) : (
              <>
                {logs.map((log, index) => (
                  <div key={`${log.seq}-${index}`} className={`log-entry log-${log.level.toLowerCase()}`}>
                    <span className="log-time">[{formatTimestamp(log.timestamp)}]</span>
                    <span className="log-message">{log.message}</span>
                  </div>
                ))}
                {isComplete && (
                  <div className="log-entry log-info" style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #e5e7eb', fontWeight: '600' }}>
                    <span className="log-time">[Final]</span>
                    <span className="log-message">✅ Sync completed successfully! All {logs.length} log entries displayed above.</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="sync-dialog-actions">
          {isComplete && (
            <button 
              className="btn-primary" 
              onClick={() => {
                if (onComplete) {
                  onComplete(progress)
                }
                onClose()
              }}
            >
              View Dashboard
            </button>
          )}
          {isFailed && (
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Retry Sync
            </button>
          )}
          <button className="btn-secondary" onClick={onClose}>
            {isRunning || isStarting ? 'Close (sync continues)' : 'Close'}
          </button>
        </div>
      </div>
    </div>
  )
}
