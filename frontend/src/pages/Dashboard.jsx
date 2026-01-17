import { useEffect, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { gmailService } from '../services/gmailService'
import SyncCompleteModal from '../components/SyncCompleteModal'
import { IconRocket, IconRefresh, IconPapers, IconCalendar, IconCheck, IconCrown, IconInfo } from '../components/icons'
import { MOCK_APPLICATIONS } from '../mock/applications.mock'
import { MOCK_DASHBOARD_STATS } from '../mock/dashboard.mock'
import '../styles/Dashboard.css'

function Dashboard() {
  const { user, isGuest } = useAuth()
  const [gmailStatus, setGmailStatus] = useState(null)
  const [syncState, setSyncState] = useState({
    isRunning: false,
    jobId: null,
    progress: null,
  })
  // 🚨 TEMPORARY GUEST MODE – mock initial state when isGuest so no loading flash, no API
  const [applications, setApplications] = useState(() => (isGuest ? MOCK_APPLICATIONS : []))
  const [stats, setStats] = useState(() => (isGuest ? MOCK_DASHBOARD_STATS : null))
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(() => !isGuest)
  const [showSyncCompleteModal, setShowSyncCompleteModal] = useState(false)
  
  const pollIntervalRef = useRef(null)
  const syncCheckRef = useRef(false)

  // Load initial data – guest uses mock only (no API). Google users call backend.
  useEffect(() => {
    if (isGuest) return
    loadInitialData()
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [isGuest])

  const loadInitialData = async () => {
    try {
      setLoading(true)
      const [statusData, statsData, appsData] = await Promise.all([
        gmailService.getStatus().catch(() => ({ connected: false })),
        gmailService.getStats().catch(() => null),
        gmailService.getApplications().catch(() => ({ applications: [], total: 0, counts: {} })),
      ])

      setGmailStatus(statusData)
      setStats(statsData)
      setApplications(appsData.applications || [])
      
      // Check if sync is running
      if (statusData.syncJobId) {
        startProgressPolling(statusData.syncJobId)
      }
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  const startProgressPolling = useCallback((jobId) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }

    setSyncState({
      isRunning: true,
      jobId,
      progress: null,
    })

    pollIntervalRef.current = setInterval(async () => {
      try {
        const progress = await gmailService.getSyncProgress(jobId)
        setSyncState(prev => ({
          ...prev,
          progress,
        }))

        // Update stats and applications in real-time
        if (progress.stats) {
          setStats(progress.stats)
        }
        if (progress.applications) {
          setApplications(progress.applications)
        }

        // Stop polling if sync is complete
        if (progress.status === 'completed' || progress.status === 'failed') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
          setSyncState(prev => ({ ...prev, isRunning: false }))
          if (progress.status === 'completed') {
            setShowSyncCompleteModal(true)
          }
          loadInitialData()
        }
      } catch (err) {
        console.error('Progress polling error:', err)
        // Continue polling even on error
      }
    }, 2000) // Poll every 2 seconds
  }, [])

  const handleStartSync = async () => {
    if (syncCheckRef.current) return // Prevent double execution
    syncCheckRef.current = true

    try {
      setError(null)
      const result = await gmailService.startSync()
      startProgressPolling(result.jobId)
    } catch (err) {
      setError(err.message || 'Failed to start sync')
      if (err.message.includes('already running')) {
        // Try to get the existing job ID
        const status = await gmailService.getStatus()
        if (status.syncJobId) {
          startProgressPolling(status.syncJobId)
        }
      }
    } finally {
      syncCheckRef.current = false
    }
  }

  if (loading) {
    return <div className="dashboard-loading">Loading dashboard...</div>
  }

  const displayName = user?.email
    ? user.email.split('@')[0].charAt(0).toUpperCase() + user.email.split('@')[0].slice(1)
    : (isGuest ? 'Guest' : 'User')

  if (applications.length === 0) {
    return (
      <>
        {error && <div className="error-banner">{error}</div>}
        <div className="dashboard-welcome-wrapper">
          <div className="dashboard-welcome-card neo-card">
            <div className="dashboard-welcome-icon">
              <IconRocket />
            </div>
            <h1>Welcome, {displayName} to JobPulse AI</h1>
            <p>
              {displayName}, it looks like you haven&apos;t synced your emails yet. Connect your Gmail account to automatically track your job applications.
            </p>
            <button
              type="button"
              onClick={handleStartSync}
              disabled={syncState.isRunning}
              className="dashboard-welcome-sync-btn"
            >
              {syncState.isRunning ? 'Syncing...' : 'Sync Emails'}
              <IconRefresh />
            </button>
          </div>
        </div>
        {showSyncCompleteModal && (
          <SyncCompleteModal progress={syncState.progress} onClose={() => setShowSyncCompleteModal(false)} />
        )}
      </>
    )
  }

  const total = stats?.total ?? 0
  const active = stats?.applied ?? 0
  const interviews = stats?.interview ?? 0
  const offers = stats?.offer ?? 0
  const recentApps = applications.slice(0, 5)

  const chartData = [
    { key: 'applied', label: 'Applied', value: stats?.applied ?? 0 },
    { key: 'interview', label: 'Interview', value: stats?.interview ?? 0 },
    { key: 'rejected', label: 'Rejected', value: stats?.rejected ?? 0 },
    { key: 'offer', label: 'Offer / Accepted', value: stats?.offer ?? 0 },
    { key: 'ghosted', label: 'Ghosted', value: stats?.ghosted ?? 0 },
  ]
  const maxChartVal = Math.max(...chartData.map((d) => d.value), 1)
  const yTicks = [maxChartVal, Math.ceil((3 * maxChartVal) / 4), Math.ceil(maxChartVal / 2), Math.ceil(maxChartVal / 4), 0]

  return (
    <div className="dashboard">
      {isGuest && (
        <div className="demo-banner neo-card">
          <IconInfo />
          <span>Demo Mode – Backend Disconnected</span>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      <div className="dashboard-stats">
        <div className="stat-card neo-card">
          <IconPapers className="stat-icon stat-icon-neutral" />
          <span className="stat-num">{(total || 0).toLocaleString()}</span>
          <span className="stat-label">TOTAL APPLICATIONS</span>
        </div>
        <div className="stat-card neo-card">
          <IconPapers className="stat-icon stat-icon-blue" />
          <span className="stat-num">{(active || 0).toLocaleString()}</span>
          <span className="stat-label">ACTIVE</span>
        </div>
        <div className="stat-card neo-card">
          <IconCalendar className="stat-icon stat-icon-yellow" />
          <span className="stat-num">{(interviews || 0).toLocaleString()}</span>
          <span className="stat-label">INTERVIEWS</span>
        </div>
        <div className="stat-card neo-card">
          <IconCheck className="stat-icon stat-icon-green" />
          <span className="stat-num">{(offers || 0).toLocaleString()}</span>
          <span className="stat-label">OFFERS</span>
        </div>
      </div>

      <div className="dashboard-middle">
        <div className="dashboard-chart-card neo-card">
          <div className="chart-header">
            <div>
              <h2>Application Overview</h2>
              <p>Current status distribution</p>
            </div>
            {!isGuest && (
              <button
                type="button"
                className="chart-sync-btn"
                onClick={handleStartSync}
                disabled={syncState.isRunning}
              >
                {syncState.isRunning ? 'Syncing...' : 'Sync'}
              </button>
            )}
          </div>
          <div className="chart-wrapper">
            <div className="chart-plot">
              <div className="chart-grid">
                <span className="chart-grid-line" />
                <span className="chart-grid-line" />
                <span className="chart-grid-line" />
              </div>
              <div className="chart-row">
                <div className="chart-y-axis">
                  {yTicks.map((n, i) => (
                    <span key={i}>{n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toLocaleString()}</span>
                  ))}
                </div>
                <div className="chart-bars">
                  {chartData.map((d) => {
                    const pct = d.value > 0 ? Math.max((d.value / maxChartVal) * 100, 8) : 0
                    return (
                      <div key={d.key} className="chart-bar-col">
                        <span className="chart-bar-spacer" />
                        {d.value > 0 && <span className="chart-bar-value">{d.value.toLocaleString()}</span>}
                        <div className={`chart-bar chart-bar-${d.key}`} style={{ height: `${pct}%` }} />
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
            <div className="chart-labels">
              {chartData.map((d) => (
                <span key={d.key}>{d.label}</span>
              ))}
            </div>
            <div className="chart-legend">
              {chartData.map((d) => (
                <div key={d.key} className="chart-legend-item">
                  <span className={`chart-legend-dot chart-legend-dot-${d.key}`} />
                  <span>{d.label}</span>
                  <span className="chart-legend-val">{d.value.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="dashboard-profile neo-card">
          <div className="profile-avatar">{user?.email?.charAt(0).toUpperCase() || 'U'}</div>
          <div className="profile-name">{displayName}</div>
          <div className="profile-email">{user?.email || ''}</div>
          <div className="profile-role">
            <IconCrown />
            <span>Editor</span>
          </div>
        </div>
      </div>

      <div className="dashboard-recent neo-card">
        <div className="recent-header">
          <h2>Recent Activity</h2>
          <Link to="/applications" className="recent-viewall">View All</Link>
        </div>
        <div className="recent-list">
          {recentApps.length === 0 ? (
            <p className="recent-empty">No recent activity.</p>
          ) : (
            recentApps.map((app, i) => (
              <div key={app.id || i} className="recent-item">
                <span className="recent-company">{app.company || 'Unknown'}</span>
                <span className="recent-role">{app.role || ''}</span>
                <span className={`status-badge status-${(app.status || '').toLowerCase()}`}>{app.status || '—'}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {showSyncCompleteModal && (
        <SyncCompleteModal
          progress={syncState.progress}
          onClose={() => setShowSyncCompleteModal(false)}
        />
      )}
    </div>
  )
}

export default Dashboard
