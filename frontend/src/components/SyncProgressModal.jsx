import { useEffect, useRef, useState } from 'react'
import { gmailService } from '../services/gmailService'
import { IconRefresh, IconCheck, IconX, IconAlertCircle } from './icons'
import '../styles/SyncProgressModal.css'

export default function SyncProgressModal({ jobId, onClose, onComplete }) {
  console.log('🎯 SyncProgressModal component rendered with jobId:', jobId)
  
  const [progress, setProgress] = useState(null)
  const [logs, setLogs] = useState([])
  const [lastLogSeq, setLastLogSeq] = useState(0)
  const [autoScroll, setAutoScroll] = useState(true)
  const logContainerRef = useRef(null)
  const pollIntervalRef = useRef(null)
  const logPollIntervalRef = useRef(null)
  
  // Always show modal - even if no jobId yet
  console.log('🎯 Modal should be visible - jobId:', jobId, 'progress:', progress)

  // Poll progress every 1-2 seconds
  useEffect(() => {
    if (!jobId) {
      console.log('SyncProgressModal: No jobId, skipping progress polling')
      return
    }

    console.log('SyncProgressModal: Starting progress polling for jobId:', jobId)

    const pollProgress = async () => {
      try {
        console.log('Polling progress for jobId:', jobId)
        const data = await gmailService.getSyncProgress(jobId)
        console.log('Progress data received:', data)
        setProgress(data)
        
        // If completed or failed, stop polling
        if (data.state === 'COMPLETED' || data.state === 'FAILED' || data.state === 'CANCELLED') {
          console.log('Sync finished with state:', data.state)
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
          if (logPollIntervalRef.current) {
            clearInterval(logPollIntervalRef.current)
            logPollIntervalRef.current = null
          }
          if (data.state === 'COMPLETED' && onComplete) {
            onComplete(data)
          }
        }
      } catch (error) {
        console.error('Failed to poll progress:', error)
        // Don't stop polling on transient errors
      }
    }

    pollProgress() // Initial poll
    pollIntervalRef.current = setInterval(pollProgress, 2000) // Poll every 2 seconds

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [jobId, onComplete])

  // Poll logs every 1 second
  useEffect(() => {
    if (!jobId) return

    const pollLogs = async () => {
      try {
        const data = await gmailService.getSyncLogs(jobId, lastLogSeq)
        if (data.logs && data.logs.length > 0) {
          setLogs(prev => [...prev, ...data.logs])
          setLastLogSeq(data.lastSeq)
        }
      } catch (error) {
        console.error('Failed to poll logs:', error)
      }
    }

    pollLogs() // Initial poll
    logPollIntervalRef.current = setInterval(pollLogs, 1000) // Poll every 1 second

    return () => {
      if (logPollIntervalRef.current) {
        clearInterval(logPollIntervalRef.current)
      }
    }
  }, [jobId, lastLogSeq])

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

  // Show "Starting..." state if no jobId yet or no progress
  if (!jobId || !progress) {
    console.log('🟡 SyncProgressModal: Rendering starting state, jobId:', jobId, 'progress:', progress)
    return (
      <div 
        className="sync-progress-modal-overlay" 
        onClick={onClose} 
        style={{ 
          zIndex: 10000,
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'rgba(0, 0, 0, 0.6)'
        }}
      >
        <div 
          className="sync-progress-modal neo-card" 
          onClick={(e) => e.stopPropagation()} 
          style={{ 
            zIndex: 10001,
            position: 'relative',
            backgroundColor: 'var(--bg-primary)',
            borderRadius: '16px',
            padding: '24px',
            minWidth: '400px',
            maxWidth: '900px'
          }}
        >
          <div className="sync-progress-header">
            <div className="sync-progress-title">
              <IconRefresh className="sync-progress-spinning" />
              <h3>Starting sync...</h3>
            </div>
            <button className="sync-progress-close" onClick={onClose} aria-label="Close">
              <IconX />
            </button>
          </div>
          <p className="sync-progress-subtitle">
            {!jobId ? 'Initializing sync job...' : 'Waiting for sync to start...'}
          </p>
          
          {/* Show stats even in starting state */}
          <div className="sync-progress-stats">
            <div className="sync-progress-stat">
              <span className="stat-label">Total Emails</span>
              <span className="stat-value">—</span>
            </div>
            <div className="sync-progress-stat">
              <span className="stat-label">Fetched</span>
              <span className="stat-value">0</span>
            </div>
            <div className="sync-progress-stat">
              <span className="stat-label">Classified</span>
              <span className="stat-value">0</span>
            </div>
            <div className="sync-progress-stat">
              <span className="stat-label">Stored</span>
              <span className="stat-value">0</span>
            </div>
            <div className="sync-progress-stat">
              <span className="stat-label">Skipped</span>
              <span className="stat-value">0</span>
            </div>
            <div className="sync-progress-stat">
              <span className="stat-label">ETA</span>
              <span className="stat-value">Calculating...</span>
            </div>
          </div>
          
          <div className="sync-progress-logs-section">
            <div className="sync-progress-logs-header">
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
            <div className="sync-progress-logs">
              <div className="log-entry">
                {!jobId ? 'Creating sync job...' : `Job ID: ${jobId}. Waiting for progress...`}
              </div>
            </div>
          </div>
          
          <div className="sync-progress-actions">
            <button className="btn-secondary" onClick={onClose}>
              Close (sync continues)
            </button>
          </div>
        </div>
      </div>
    )
  }

  const isComplete = progress.state === 'COMPLETED'
  const isFailed = progress.state === 'FAILED'
  const isRunning = progress.state === 'RUNNING' || progress.state === 'QUEUED'

  console.log('🟢 SyncProgressModal: Rendering with progress:', progress.state, 'jobId:', jobId)

  return (
    <div 
      className="sync-progress-modal-overlay" 
      onClick={onClose} 
      style={{ 
        zIndex: 10000,
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.6)'
      }}
    >
      <div 
        className="sync-progress-modal neo-card" 
        onClick={(e) => e.stopPropagation()} 
        style={{ 
          zIndex: 10001,
          position: 'relative',
          backgroundColor: 'var(--bg-primary)',
          borderRadius: '16px',
          padding: '24px',
          minWidth: '400px',
          maxWidth: '900px'
        }}
      >
        {/* Header */}
        <div className="sync-progress-header">
          <div className="sync-progress-title">
            {isRunning && <IconRefresh className="sync-progress-spinning" />}
            {isComplete && <IconCheck className="sync-progress-success" />}
            {isFailed && <IconAlertCircle className="sync-progress-error" />}
            <h3>
              {isRunning && 'Syncing your Gmail...'}
              {isComplete && 'Sync Complete'}
              {isFailed && 'Sync Failed'}
            </h3>
          </div>
          <button className="sync-progress-close" onClick={onClose} aria-label="Close">
            <IconX />
          </button>
        </div>

        {/* Subtitle */}
        <p className="sync-progress-subtitle">
          {isRunning && 'Please wait while we sync your data.'}
          {isComplete && 'Your Gmail has been successfully synced.'}
          {isFailed && progress.errorMessage}
        </p>

        {/* Progress Bar */}
        {isRunning && (
          <div className="sync-progress-bar-container">
            <div className="sync-progress-bar">
              <div
                className="sync-progress-bar-fill"
                style={{ width: `${Math.min(progress.percent || 0, 100)}%` }}
              />
            </div>
            <div className="sync-progress-bar-text">
              {progress.totalEmailsEstimated
                ? `Emails processed: ${progress.emailsFetched.toLocaleString()} / ${progress.totalEmailsEstimated.toLocaleString()}`
                : `Processing: ${progress.emailsFetched.toLocaleString()} emails...`}
            </div>
          </div>
        )}

        {/* Stats Grid */}
        <div className="sync-progress-stats">
          <div className="sync-progress-stat">
            <span className="stat-label">Total Emails</span>
            <span className="stat-value">{progress.totalEmailsEstimated?.toLocaleString() || '—'}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Fetched</span>
            <span className="stat-value">{progress.emailsFetched.toLocaleString()}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Classified</span>
            <span className="stat-value">{progress.emailsClassified.toLocaleString()}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Stored</span>
            <span className="stat-value">{progress.applicationsCreatedOrUpdated.toLocaleString()}</span>
          </div>
          <div className="sync-progress-stat">
            <span className="stat-label">Skipped</span>
            <span className="stat-value">{progress.skipped.toLocaleString()}</span>
          </div>
          {isRunning && progress.etaSeconds && (
            <div className="sync-progress-stat">
              <span className="stat-label">ETA</span>
              <span className="stat-value">{formatTime(progress.etaSeconds)}</span>
            </div>
          )}
        </div>

        {/* Category Breakdown */}
        {progress.categoryCounts && Object.keys(progress.categoryCounts).length > 0 && (
          <div className="sync-progress-categories">
            <h4>Applications by Category</h4>
            <div className="sync-progress-category-badges">
              {Object.entries(progress.categoryCounts).map(([category, count]) => (
                <span key={category} className="category-badge">
                  {category}: {count}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Logs Panel */}
        <div className="sync-progress-logs-section">
          <div className="sync-progress-logs-header">
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
            className="sync-progress-logs"
            ref={logContainerRef}
            onScroll={() => {
              // Stop auto-scroll if user scrolls up
              if (logContainerRef.current) {
                const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current
                if (scrollTop + clientHeight < scrollHeight - 50) {
                  setAutoScroll(false)
                }
              }
            }}
          >
            {logs.length === 0 ? (
              <div className="log-entry">Waiting for logs...</div>
            ) : (
              logs.map((log, index) => (
                <div key={`${log.seq}-${index}`} className={`log-entry log-${log.level.toLowerCase()}`}>
                  <span className="log-time">[{formatTimestamp(log.timestamp)}]</span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="sync-progress-actions">
          <button className="btn-secondary" onClick={onClose}>
            {isRunning ? 'Close (sync continues)' : 'Close'}
          </button>
          {isFailed && (
            <button className="btn-primary" onClick={() => window.location.reload()}>
              Retry Sync
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
