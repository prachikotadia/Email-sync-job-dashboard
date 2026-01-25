import { useEffect, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useProfileImage } from '../context/ProfileImageContext'
import { useProfileLinks } from '../context/ProfileLinksContext'
import { gmailService } from '../services/gmailService'
import SyncLogModal from '../components/SyncLogModal'
import SyncOptionsModal from '../components/SyncOptionsModal'
import { useGmailSyncProgress } from '../hooks/useGmailSyncProgress'
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
  const { links, linksObject } = useProfileLinks()
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
  const [showSyncLogModal, setShowSyncLogModal] = useState(false)
  const [showSyncOptionsModal, setShowSyncOptionsModal] = useState(false)
  const [currentSyncId, setCurrentSyncId] = useState(null)
  const [selectedSyncRange, setSelectedSyncRange] = useState(null)
  
  const syncCheckRef = useRef(false)
  
  // Use SSE hook for progress updates (NO POLLING)
  // STATELESS: Hook handles fetchSyncStatus on refresh, reconnection, etc.
  const { event: progressEvent, connected, reconnecting, error: sseError, syncStatus } = useGmailSyncProgress(currentSyncId)

  // Load initial data – guest uses mock only (no API). Google users call backend.
  useEffect(() => {
    if (isGuest) return
    loadInitialData()
  }, [isGuest])
  
  // Update sync state from SSE events - accumulate progress
  useEffect(() => {
    if (!progressEvent) return
    
    const phase = progressEvent.phase
    const isRunning = !progressEvent.done && phase !== 'failed' && phase !== 'canceled'
    
    // Accumulate logs and update progress
    setSyncState(prevState => {
      const existingLogs = prevState.progress?.logs || []
      
      // Add detailed log message if available (for real-time UI display)
      const logsToAdd = []
      
      // Add log_message if present (more detailed than message)
      if (progressEvent.log_message) {
        const detailedLog = {
          time: progressEvent.ts,
          message: progressEvent.log_message,
          type: progressEvent.log_type || progressEvent.level || 'info',
          email_id: progressEvent.email_id,
          retry_count: progressEvent.retry_count,
          retry_after_seconds: progressEvent.retry_after_seconds
        }
        logsToAdd.push(detailedLog)
      }
      
      // Also add regular message if different from log_message
      const regularLog = {
        time: progressEvent.ts,
        message: progressEvent.message,
        type: progressEvent.level || 'info',
        email_id: progressEvent.email_id,
        retry_count: progressEvent.retry_count,
        retry_after_seconds: progressEvent.retry_after_seconds
      }
      
      // Only add regular log if it's different from log_message
      if (!progressEvent.log_message || progressEvent.message !== progressEvent.log_message) {
        logsToAdd.push(regularLog)
      }
      
      // Add logs from event.logs array if present
      if (progressEvent.logs && Array.isArray(progressEvent.logs)) {
        logsToAdd.push(...progressEvent.logs)
      }
      
      // Filter out duplicates and add new logs
      const updatedLogs = [...existingLogs]
      logsToAdd.forEach(newLog => {
        const isNewLog = !existingLogs.some(log => 
          log.time === newLog.time && 
          log.message === newLog.message &&
          log.email_id === newLog.email_id
        )
        if (isNewLog) {
          updatedLogs.push(newLog)
        }
      })
      
      // Keep only last 200 logs for performance
      const finalLogs = updatedLogs.slice(-200)
      
      // Get counts from event - use the latest values
      const counts = progressEvent.counts || {}
      
      return {
        isRunning,
        jobId: progressEvent.sync_id,
        progress: {
          status: phase === 'done' ? 'completed' : phase === 'failed' ? 'failed' : phase === 'canceled' ? 'canceled' : 'running',
          state: phase.toUpperCase(),
          total_emails: counts.total_estimated || counts.listed || 0,
          total_scanned: counts.listed || counts.total_estimated || 0,
          processed_emails: counts.fetched || counts.parsed || 0,
          emails_fetched: counts.fetched || 0,
          total_fetched: counts.fetched || 0,
          applications_found: counts.saved || counts.classified || 0,
          skipped: counts.skipped || 0,
          failed: counts.failed || 0,
          counts: {
            applied: 0,
            rejected: 0,
            interview: 0,
            offer: 0,
            ghosted: 0
          },
          logs: updatedLogs.slice(-200), // Keep last 200 logs
          email_entries: prevState.progress?.email_entries || [],
          // Store raw event for debugging
          lastEvent: progressEvent,
          logs: finalLogs
        }
      }
    })
    
    // If done, reload data
    if (progressEvent.done && phase === 'done') {
      setTimeout(() => loadInitialData(), 1000) // Small delay to ensure DB is updated
    }
  }, [progressEvent])

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
      
      // Check if sync is running - connect to SSE
      if (statusData.syncJobId) {
        setCurrentSyncId(statusData.syncJobId)
        setSyncState({
          isRunning: true,
          jobId: statusData.syncJobId,
          progress: null
        })
        setShowSyncLogModal(true)
      }
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  // NO POLLING - SSE hook handles all progress updates

  const handleCancelSync = async () => {
    if (!syncState.jobId) return
    
    try {
      await gmailService.stopSync(syncState.jobId)
      // UI will update when SSE receives CANCELED event
      // Don't optimistically update here - wait for SSE confirmation
    } catch (err) {
      setError(err.message || 'Failed to cancel sync')
    }
  }

  const handleStartSync = () => {
    if (syncCheckRef.current || syncState.isRunning) {
      // If already running, just show the modal
      if (syncState.isRunning && syncState.jobId) {
        setShowSyncLogModal(true)
      }
      return
    }
    // Show sync options modal first
    setShowSyncOptionsModal(true)
  }

  const handleSyncOptionsConfirm = async (options) => {
    setShowSyncOptionsModal(false)
    setSelectedSyncRange(options)
    syncCheckRef.current = true

    try {
      setError(null)
      // Show log modal IMMEDIATELY before making API call
      setShowSyncLogModal(true)
      setSyncState({
        isRunning: true,
        jobId: null,
        progress: null,
      })
      
      const result = await gmailService.startSync({
        range: options.range,
        months: options.months
      })
      // Contract: { "sync_id": "uuid", "status": "queued" }
      const syncId = result.sync_id || result.jobId
      if (syncId) {
        setCurrentSyncId(syncId)
        setSyncState({
          isRunning: true,
          jobId: syncId,
          progress: null
        })
      } else {
        throw new Error('No sync_id returned from server')
      }
    } catch (err) {
      setError(err.message || 'Failed to start sync')
      setSyncState(prev => ({ ...prev, isRunning: false }))
      if (err.message.includes('already running')) {
        // Try to get the existing sync ID
        try {
          const status = await gmailService.getStatus()
          if (status.syncJobId) {
            setCurrentSyncId(status.syncJobId)
            setSyncState({
              isRunning: true,
              jobId: status.syncJobId,
              progress: null
            })
            setShowSyncLogModal(true)
          }
        } catch (statusErr) {
          console.error('Failed to get sync status:', statusErr)
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
        {showSyncOptionsModal && (
          <SyncOptionsModal
            isOpen={showSyncOptionsModal}
            onClose={() => setShowSyncOptionsModal(false)}
            onConfirm={handleSyncOptionsConfirm}
          />
        )}
        {showSyncLogModal && (
          <SyncLogModal
            progress={syncState.progress}
            isRunning={syncState.isRunning}
            onClose={() => {
              setShowSyncLogModal(false)
            }}
            onCancel={handleCancelSync}
            jobId={syncState.jobId}
            connected={connected}
            reconnecting={reconnecting}
            sseError={sseError}
            syncStatus={syncStatus}
            selectedRange={selectedSyncRange}
          />
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
              {((links && links.length > 0) || (linksObject && (linksObject.linkedin || linksObject.portfolio || linksObject.indeed || linksObject.github || linksObject.website || linksObject.other))) && (
                <div className="profile-links-section">
                  <div className="profile-links-label">Links</div>
                  <div className="profile-links-list">
                    {/* Render links from array (new format) */}
                    {links && links.length > 0 ? (
                      links.map((link) => {
                        if (link.type === 'linkedin') {
                          return (
                            <a
                              key={link.id}
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="profile-link-item"
                              title="LinkedIn"
                            >
                              <IconLinkedIn />
                            </a>
                          )
                        } else if (link.type === 'github') {
                          return (
                            <a
                              key={link.id}
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="profile-link-item"
                              title="GitHub"
                            >
                              <IconGithub />
                            </a>
                          )
                        } else if (link.type === 'portfolio') {
                          return (
                            <a
                              key={link.id}
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="profile-link-item"
                              title={link.label || 'Portfolio'}
                            >
                              <IconGlobe />
                            </a>
                          )
                        } else if (link.type === 'custom') {
                          return (
                            <a
                              key={link.id}
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="profile-link-item"
                              title={link.label || 'Custom Link'}
                            >
                              <IconLink />
                            </a>
                          )
                        }
                        return null
                      })
                    ) : (
                      /* Legacy format (linksObject) - for backward compatibility */
                      <>
                        {linksObject?.linkedin && (
                          <a 
                            href={linksObject.linkedin.startsWith('http') ? linksObject.linkedin : `https://${linksObject.linkedin}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="profile-link-item"
                            title="LinkedIn"
                          >
                            <IconLinkedIn />
                          </a>
                        )}
                        {linksObject?.portfolio && (
                          <a 
                            href={linksObject.portfolio.startsWith('http') ? linksObject.portfolio : `https://${linksObject.portfolio}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="profile-link-item"
                            title="Portfolio"
                          >
                            <IconGlobe />
                          </a>
                        )}
                        {linksObject?.indeed && (
                          <a 
                            href={linksObject.indeed.startsWith('http') ? linksObject.indeed : `https://${linksObject.indeed}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="profile-link-item"
                            title="Indeed"
                          >
                            <IconLink />
                          </a>
                        )}
                        {linksObject?.github && (
                          <a 
                            href={linksObject.github.startsWith('http') ? linksObject.github : `https://${linksObject.github}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="profile-link-item"
                            title="GitHub"
                          >
                            <IconGithub />
                          </a>
                        )}
                        {linksObject?.website && (
                          <a 
                            href={linksObject.website.startsWith('http') ? linksObject.website : `https://${linksObject.website}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="profile-link-item"
                            title="Website"
                          >
                            <IconGlobe />
                          </a>
                        )}
                        {linksObject?.other && (
                          <a 
                            href={linksObject.other.startsWith('http') ? linksObject.other : `https://${linksObject.other}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="profile-link-item"
                            title="Other"
                          >
                            <IconLink />
                          </a>
                        )}
                      </>
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

      {showSyncOptionsModal && (
        <SyncOptionsModal
          isOpen={showSyncOptionsModal}
          onClose={() => setShowSyncOptionsModal(false)}
          onConfirm={handleSyncOptionsConfirm}
        />
      )}
      {showSyncLogModal && (
        <SyncLogModal
          progress={syncState.progress}
          isRunning={syncState.isRunning}
          connected={connected}
          reconnecting={reconnecting}
          sseError={sseError}
          onCancel={handleCancelSync}
          jobId={syncState.jobId}
          syncStatus={syncStatus}
          selectedRange={selectedSyncRange}
          onClose={() => {
            setShowSyncLogModal(false)
            // Don't clear syncId - allow reconnection if user reopens
          }}
        />
      )}
    </div>
  )
}

export default Dashboard
