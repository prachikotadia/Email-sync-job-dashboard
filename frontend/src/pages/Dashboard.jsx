import { useEffect, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useProfileImage } from '../context/ProfileImageContext'
import { useProfileLinks } from '../context/ProfileLinksContext'
import { gmailService } from '../services/gmailService'
import SyncCompleteModal from '../components/SyncCompleteModal'
import SyncLogModal from '../components/SyncLogModal'
import SyncProgressModal from '../components/SyncProgressModal'
import SyncDialog from '../components/SyncDialog'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, LabelList, Cell } from 'recharts'
import { 
  IconRocket, 
  IconRefresh, 
  IconPapers, 
  IconCalendar, 
  IconCheck, 
  IconCrown, 
  IconInfo,
  IconChart,
  IconActivity,
  IconArrowRight,
  IconBriefcase,
  IconUser,
  IconMail,
  IconTrendingUp,
  IconLinkedIn,
  IconGithub,
  IconLink,
  IconGlobe
} from '../components/icons'
import { MOCK_APPLICATIONS } from '../mock/applications.mock'
import { MOCK_DASHBOARD_STATS, MOCK_CHART_DATA } from '../mock/dashboard.mock'
import '../styles/Dashboard.css'

function Dashboard() {
  const { user, isGuest } = useAuth()
  const { profileImage } = useProfileImage()
  const { links } = useProfileLinks()
  const [gmailStatus, setGmailStatus] = useState(null)
  const [syncState, setSyncState] = useState({
    isRunning: false,
    syncId: null, // Use sync_id consistently
    progress: null,
  })
  // 🚨 TEMPORARY GUEST MODE – mock initial state when isGuest so no loading flash, no API
  const [applications, setApplications] = useState(() => (isGuest ? MOCK_APPLICATIONS : []))
  const [stats, setStats] = useState(() => (isGuest ? MOCK_DASHBOARD_STATS : null))
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(() => !isGuest)
  const [showSyncCompleteModal, setShowSyncCompleteModal] = useState(false)
  const [showSyncLogModal, setShowSyncLogModal] = useState(false)
  const [syncJobId, setSyncJobId] = useState(null)
  const [showSyncProgressModal, setShowSyncProgressModal] = useState(false)
  const [showSyncDialog, setShowSyncDialog] = useState(false)
  
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
    if (isGuest) return

    try {
      setLoading(true)
      // Use Promise.allSettled to handle partial failures gracefully
      const results = await Promise.allSettled([
        gmailService.getStatus().catch(() => ({ connected: false })),
        gmailService.getStats().catch(() => null),
        gmailService.getApplications().catch(() => ({ applications: [], total: 0, counts: {} })),
      ])

      const [statusResult, statsResult, appsResult] = results
      
      // Only update state if requests succeeded
      if (statusResult.status === 'fulfilled') {
        setGmailStatus(statusResult.value)
      }
      if (statsResult.status === 'fulfilled' && statsResult.value) {
        setStats(statsResult.value)
      }
      if (appsResult.status === 'fulfilled') {
        setApplications(appsResult.value.applications || [])
      }
      
      // Check if sync is running (new job-based system) - don't block on this
      try {
        const status = await gmailService.getSyncStatus()
        if (status.jobId && (status.status === 'RUNNING' || status.status === 'QUEUED')) {
          setSyncJobId(status.jobId)
          setShowSyncDialog(true)
          setShowSyncProgressModal(true)
        }
      } catch (statusErr) {
        // Ignore status check errors - non-critical
        console.log('Status check failed (non-critical):', statusErr)
      }
    } catch (err) {
      console.error('Error loading initial data:', err)
      // Don't set error state - allow partial data to display
    } finally {
      setLoading(false)
    }
  }

  const startProgressPolling = useCallback((syncId) => {
    // STRICT GUARD: Do not poll if syncId is undefined/null/empty
    if (!syncId || syncId === 'undefined' || syncId === 'null') {
      console.error('Cannot start polling: syncId is invalid', syncId)
      setError('Cannot start sync progress tracking: invalid sync ID')
      return
    }

    // Ensure only one interval runs at a time
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }

    setSyncState({
      isRunning: true,
      syncId,
      progress: null,
    })

    let consecutiveErrors = 0
    const MAX_CONSECUTIVE_ERRORS = 3

    pollIntervalRef.current = setInterval(async () => {
      // Double-check syncId is still valid
      if (!syncId || syncId === 'undefined' || syncId === 'null') {
        console.error('Polling stopped: syncId became invalid')
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
        }
        setSyncState(prev => ({ ...prev, isRunning: false }))
        return
      }

      try {
        const progress = await gmailService.getSyncProgress(syncId)
        
        // Reset error counter on success
        consecutiveErrors = 0
        setError(null)

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
            // Keep log modal open to show completion, then show completion modal
            setTimeout(() => {
              setShowSyncLogModal(false)
              setShowSyncCompleteModal(true)
            }, 2000)
          } else {
            // Keep log modal open to show failure
            setShowSyncLogModal(true)
          }
          loadInitialData()
        }
      } catch (err) {
        consecutiveErrors++
        const errorMessage = err.message || 'Failed to get sync progress'
        console.error('Progress polling error:', errorMessage)
        
        // Stop polling on service unavailable (503) or too many errors
        if (errorMessage.includes('service unavailable') || consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          console.error('Stopping polling due to persistent errors')
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
          setSyncState(prev => ({ ...prev, isRunning: false }))
          setError(errorMessage)
        } else {
          // Show error but continue polling for transient errors
          setError(`Sync progress error: ${errorMessage}`)
        }
      }
    }, 2000) // Poll every 2 seconds
  }, [])

  const handleStartSync = async () => {
    // Prevent double execution
    if (syncCheckRef.current) {
      console.log('Sync check already in progress')
      return
    }
    
    // If modal is already open with a running job, just focus it
    if (showSyncProgressModal && syncJobId) {
      console.log('Sync modal already open with jobId:', syncJobId, '- focusing existing modal')
      // Modal is already showing, just return
      return
    }
    
    syncCheckRef.current = true

    try {
      setError(null)
      console.log('🟢 Starting sync - opening modal immediately...')
      
      // CRITICAL: Show dialog FIRST, before any API calls
      // This ensures the dialog appears instantly when button is clicked
      setShowSyncDialog(true)
      setShowSyncProgressModal(true) // Keep for backward compatibility
      setSyncJobId(null) // Reset jobId so dialog shows "Starting..." state
      
      // Small delay to ensure React has rendered the dialog
      await new Promise(resolve => setTimeout(resolve, 50))
      
      // Check for existing job first
      console.log('Checking for existing sync job...')
      try {
        const status = await gmailService.getSyncStatus()
        console.log('Sync status:', status)
        
        if (status.jobId && (status.status === 'RUNNING' || status.status === 'QUEUED')) {
          // Attach to existing job
          console.log('Attaching to existing job:', status.jobId)
          setSyncJobId(status.jobId)
          setShowSyncDialog(true)
          return
        }
      } catch (statusErr) {
        console.log('Status check failed, proceeding with new sync:', statusErr)
        // Continue to start new sync if status check fails
      }
      
      // Start new sync
      console.log('Starting new sync job...')
      const result = await gmailService.startSync()
      console.log('Sync started, result:', result)
      
      if (!result.jobId) {
        throw new Error('Sync started but no jobId returned')
      }
      
      console.log('Setting jobId:', result.jobId)
      setSyncJobId(result.jobId)
      setShowSyncDialog(true) // Ensure dialog is open
    } catch (err) {
      console.error('Sync start error:', err)
      const errorMessage = err.message || 'Failed to start sync'
      setError(errorMessage)
      // Keep modal open to show error
      // setShowSyncProgressModal(false)
      // setSyncJobId(null)
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
        {showSyncLogModal && (
          <SyncLogModal
            progress={syncState.progress}
            isRunning={syncState.isRunning}
            onClose={() => setShowSyncLogModal(false)}
          />
        )}
        {showSyncCompleteModal && (
          <SyncCompleteModal progress={syncState.progress} onClose={() => setShowSyncCompleteModal(false)} />
        )}
      </>
    )
  }

  const total = stats?.total ?? MOCK_DASHBOARD_STATS.total
  const active = stats?.applied ?? MOCK_DASHBOARD_STATS.applied
  const interviews = stats?.interview ?? MOCK_DASHBOARD_STATS.interview
  const offers = stats?.offer ?? MOCK_DASHBOARD_STATS.offer
  const recentApps = applications.slice(0, 5)

  // Format data for Recharts BarChart
  const chartData = [
    { name: 'Applied', value: stats?.applied ?? MOCK_CHART_DATA.applied, color: '#7c3aed' },
    { name: 'Interview', value: stats?.interview ?? MOCK_CHART_DATA.interview, color: '#2563eb' },
    { name: 'Rejected', value: stats?.rejected ?? MOCK_CHART_DATA.rejected, color: '#dc2626' },
    { name: 'Offer / Accepted', value: stats?.offer ?? MOCK_CHART_DATA.offer, color: '#16a34a' },
    { name: 'Ghosted', value: stats?.ghosted ?? MOCK_CHART_DATA.ghosted, color: '#64748b' },
  ]
  
  // Calculate dynamic Y-axis max with proper rounding
  const dataMax = Math.max(...chartData.map((d) => d.value), 1)
  
  // Round up to clean step (50 for small numbers, 100 for larger)
  const step = dataMax < 200 ? 50 : 100
  const dynamicMax = Math.ceil(dataMax / step) * step
  
  // Custom label renderer for values above bars
  const renderCustomLabel = (props) => {
    const { x, y, width, value } = props
    if (!value || value === 0) return null
    return (
      <text
        x={x + width / 2}
        y={y - 8}
        fill="var(--text)"
        textAnchor="middle"
        fontSize="0.875rem"
        fontWeight="700"
        style={{ textShadow: '0 1px 3px rgba(0, 0, 0, 0.4)' }}
      >
        {value.toLocaleString()}
      </text>
    )
  }

  return (
    <div className="dashboard-professional">
      {isGuest && (
        <div className="demo-banner neo-card animate-fade-in">
          <IconInfo />
          <span>Demo Mode – Backend Disconnected</span>
        </div>
      )}

      {error && <div className="error-banner animate-slide-down">{error}</div>}

      {/* Professional Header Section */}
      <div className="dashboard-header-section">
        <div className="dashboard-title-area">
          <h1 className="dashboard-main-title">Dashboard</h1>
          <p className="dashboard-subtitle">Track your job application pipeline</p>
        </div>
        {!isGuest && (
          <div className="dashboard-actions">
            <button
              type="button"
              className="dashboard-action-btn"
              onClick={handleStartSync}
              disabled={syncState.isRunning}
            >
              <IconRefresh className={syncState.isRunning ? 'spinning' : ''} />
              <span>{syncState.isRunning ? 'Syncing...' : 'Sync Now'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Stats Grid - Perfect 4-Column Layout */}
      <div className="dashboard-stats-perfect">
        <div className="stat-card-perfect stat-card-primary animate-stat-card" style={{ animationDelay: '0ms' }}>
          <div className="stat-card-glow" />
          <div className="stat-card-header">
            <div className="stat-icon-container">
              <IconPapers className="stat-icon-main" />
            </div>
            <div className="stat-change-badge">+12%</div>
          </div>
          <div className="stat-card-body">
            <div className="stat-number-primary">{(total || 0).toLocaleString()}</div>
            <div className="stat-label-primary">Total Applications</div>
          </div>
        </div>

        <div className="stat-card-perfect stat-card-secondary animate-stat-card" style={{ animationDelay: '100ms' }}>
          <div className="stat-card-glow" />
          <div className="stat-card-header">
            <div className="stat-icon-container">
              <IconActivity className="stat-icon-main" />
            </div>
          </div>
          <div className="stat-card-body">
            <div className="stat-number-secondary">{(active || 0).toLocaleString()}</div>
            <div className="stat-label-secondary">Active</div>
          </div>
        </div>

        <div className="stat-card-perfect stat-card-tertiary animate-stat-card" style={{ animationDelay: '200ms' }}>
          <div className="stat-card-glow" />
          <div className="stat-card-header">
            <div className="stat-icon-container">
              <IconCalendar className="stat-icon-main" />
            </div>
          </div>
          <div className="stat-card-body">
            <div className="stat-number-tertiary">{(interviews || 0).toLocaleString()}</div>
            <div className="stat-label-tertiary">Interviews</div>
          </div>
        </div>

        <div className="stat-card-perfect stat-card-quaternary animate-stat-card" style={{ animationDelay: '300ms' }}>
          <div className="stat-card-glow" />
          <div className="stat-card-header">
            <div className="stat-icon-container">
              <IconCheck className="stat-icon-main" />
            </div>
          </div>
          <div className="stat-card-body">
            <div className="stat-number-quaternary">{(offers || 0).toLocaleString()}</div>
            <div className="stat-label-quaternary">Offers</div>
          </div>
        </div>
      </div>

      {/* Main Content - Perfect 2-Column Layout */}
      <div className="dashboard-content-perfect">
        {/* Left Column: Chart */}
        <div className="dashboard-content-left">
          <div className="content-card-perfect chart-card-perfect animate-slide-up">
            <div className="content-card-header">
              <div className="content-card-title-group">
                <div className="content-card-icon">
                  <IconChart />
                </div>
                <div>
                  <h2 className="content-card-title">Application Overview</h2>
                  <p className="content-card-subtitle">Status distribution</p>
                </div>
              </div>
              {!isGuest && (
                <button
                  type="button"
                  className="content-card-action"
                  onClick={handleStartSync}
                  disabled={syncState.isRunning}
                >
                  <IconRefresh className={syncState.isRunning ? 'spinning' : ''} />
                  <span>{syncState.isRunning ? 'Syncing...' : 'Sync'}</span>
                </button>
              )}
            </div>
            <div className="chart-wrapper-recharts">
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={chartData}
                  margin={{ top: 20, right: 20, bottom: 60, left: 20 }}
                  barCategoryGap="20%"
                >
                  <CartesianGrid 
                    strokeDasharray="3 3" 
                    stroke="rgba(255, 255, 255, 0.08)" 
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'var(--text-muted)', fontSize: '0.8125rem', fontWeight: 600 }}
                    angle={0}
                    textAnchor="middle"
                    height={60}
                    interval={0}
                    tickMargin={8}
                  />
                  <YAxis
                    domain={[0, dynamicMax]}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 700 }}
                    tickFormatter={(value) => value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toLocaleString()}
                    width={50}
                  />
                  <Bar
                    dataKey="value"
                    radius={[8, 8, 0, 0]}
                    minPointSize={6}
                    barSize={52}
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                    <LabelList 
                      dataKey="value" 
                      content={renderCustomLabel}
                      position="top"
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right Column: Profile & Activity */}
        <div className="dashboard-content-right">
          {/* Profile Card */}
          <div className="content-card-perfect profile-card-perfect animate-slide-up" style={{ animationDelay: '150ms' }}>
            <div className="content-card-header">
              <div className="content-card-title-group">
                <div className="content-card-icon">
                  <IconUser />
                </div>
                <h3 className="content-card-title">Profile</h3>
              </div>
            </div>
            <div className="profile-card-body">
              <div className="profile-avatar-perfect">
                {profileImage ? (
                  <div className="profile-avatar-circle profile-avatar-with-image">
                    <img src={profileImage} alt="Profile" className="profile-avatar-img" />
                  </div>
                ) : (
                  <div className="profile-avatar-circle">
                    {user?.email?.charAt(0).toUpperCase() || 'U'}
                  </div>
                )}
                <div className="profile-status-dot" />
              </div>
              <div className="profile-info">
                <div className="profile-name-perfect">{displayName}</div>
                <div className="profile-email-perfect">
                  <IconMail />
                  <span>{user?.email || ''}</span>
                </div>
                <div className="profile-role-perfect">
                  <IconCrown />
                  <span>Editor</span>
                </div>
              </div>
              <div className="profile-stat-perfect">
                <IconBriefcase />
                <div>
                  <div className="profile-stat-number">{total || 0}</div>
                  <div className="profile-stat-text">Applications</div>
                </div>
              </div>
              
              {/* Profile Links */}
              {(links.linkedin || links.portfolio || links.indeed || links.github || links.website || links.other) && (
                <div className="profile-links-section">
                  <div className="profile-links-label">Links</div>
                  <div className="profile-links-list">
                    {links.linkedin && (
                      <a 
                        href={links.linkedin.startsWith('http') ? links.linkedin : `https://${links.linkedin}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="profile-link-item"
                        title="LinkedIn"
                      >
                        <IconLinkedIn />
                      </a>
                    )}
                    {links.portfolio && (
                      <a 
                        href={links.portfolio.startsWith('http') ? links.portfolio : `https://${links.portfolio}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="profile-link-item"
                        title="Portfolio"
                      >
                        <IconGlobe />
                      </a>
                    )}
                    {links.indeed && (
                      <a 
                        href={links.indeed.startsWith('http') ? links.indeed : `https://${links.indeed}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="profile-link-item"
                        title="Indeed"
                      >
                        <IconLink />
                      </a>
                    )}
                    {links.github && (
                      <a 
                        href={links.github.startsWith('http') ? links.github : `https://${links.github}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="profile-link-item"
                        title="GitHub"
                      >
                        <IconGithub />
                      </a>
                    )}
                    {links.website && (
                      <a 
                        href={links.website.startsWith('http') ? links.website : `https://${links.website}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="profile-link-item"
                        title="Website"
                      >
                        <IconGlobe />
                      </a>
                    )}
                    {links.other && (
                      <a 
                        href={links.other.startsWith('http') ? links.other : `https://${links.other}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="profile-link-item"
                        title="Other"
                      >
                        <IconLink />
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Recent Activity Card */}
          <div className="content-card-perfect activity-card-perfect animate-slide-up" style={{ animationDelay: '200ms' }}>
            <div className="content-card-header">
              <div className="content-card-title-group">
                <div className="content-card-icon">
                  <IconActivity />
                </div>
                <div>
                  <h3 className="content-card-title">Recent Activity</h3>
                  <p className="content-card-subtitle">{recentApps.length} items</p>
                </div>
              </div>
              <Link to="/applications" className="content-card-link">
                View All
                <IconArrowRight />
              </Link>
            </div>
            <div className="activity-list-perfect">
              {recentApps.length === 0 ? (
                <div className="activity-empty">
                  <IconActivity />
                  <p>No recent activity</p>
                </div>
              ) : (
                recentApps.map((app, i) => {
                  const statusIcon = app.status === 'applied' ? <IconPapers /> :
                                    app.status === 'interview' ? <IconCalendar /> :
                                    app.status === 'offer' ? <IconCheck /> :
                                    <IconBriefcase />
                  return (
                    <div 
                      key={app.id || i} 
                      className="activity-item-perfect"
                      style={{ animationDelay: `${300 + i * 50}ms` }}
                    >
                      <div className="activity-item-icon">{statusIcon}</div>
                      <div className="activity-item-info">
                        <div className="activity-company">{app.company || 'Unknown'}</div>
                        <div className="activity-role">{app.role || ''}</div>
                      </div>
                      <div className={`activity-status activity-status-${(app.status || '').toLowerCase()}`}>
                        {app.status || '—'}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* New Sync Dialog - Shows immediately on sync button click */}
      <SyncDialog
        jobId={syncJobId}
        isOpen={showSyncDialog}
        onClose={() => {
          setShowSyncDialog(false)
          // Don't clear jobId - allow reattaching if sync is still running
        }}
        onComplete={async (progress) => {
          console.log('User clicked View Dashboard, closing dialog and reloading data:', progress)
          setShowSyncDialog(false)
          setShowSyncProgressModal(false)
          // Load data in background, don't block on errors
          try {
            await loadInitialData()
          } catch (err) {
            console.error('Failed to reload data after sync:', err)
            // Don't show error to user - sync completed successfully
          }
        }}
      />
      
      {/* Legacy SyncProgressModal - kept for backward compatibility */}
      {showSyncProgressModal && !showSyncDialog && (
        <SyncProgressModal
          jobId={syncJobId}
          onClose={() => {
            setShowSyncProgressModal(false)
          }}
          onComplete={async (progress) => {
            setShowSyncProgressModal(false)
            setShowSyncCompleteModal(true)
            try {
              await loadInitialData()
            } catch (err) {
              console.error('Failed to reload data after sync:', err)
            }
          }}
        />
      )}
      {!showSyncProgressModal && console.log('🔴 NOT rendering SyncProgressModal - showSyncProgressModal is false')}
      {showSyncLogModal && (
        <SyncLogModal
          progress={syncState.progress}
          isRunning={syncState.isRunning}
          onClose={() => setShowSyncLogModal(false)}
        />
      )}
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
