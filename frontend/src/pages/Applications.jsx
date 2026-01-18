import { useEffect, useState, useMemo, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { gmailService } from '../services/gmailService'
import { IconDownload, IconList, IconGridSmall, IconBriefcase, IconSearch, IconAlertCircle, IconExternalLink } from '../components/icons'
import '../styles/Applications.css'

// Category mapping - only 5 allowed categories (uppercase from backend)
const CATEGORY_LABELS = {
  APPLIED: 'Applied',
  REJECTED: 'Rejected',
  INTERVIEW: 'Interview',
  OFFER_ACCEPTED: 'Offer / Accepted',
  GHOSTED: 'Ghosted',
}

const CATEGORY_OPTIONS = ['All Statuses', ...Object.values(CATEGORY_LABELS)]

export default function Applications() {
  const { user, isGuest } = useAuth()
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All Statuses')
  const [viewMode, setViewMode] = useState('list') // 'list' | 'grid'

  // Load applications from backend
  const loadApplications = useCallback(async () => {
    if (isGuest) {
      setApplications([])
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const res = await gmailService.getApplications()
      setApplications(res.applications || [])
    } catch (err) {
      console.error('Error loading applications:', err)
      setError(err.message || 'Failed to load applications')
      setApplications([])
    } finally {
      setLoading(false)
    }
  }, [isGuest])

  // Initial load
  useEffect(() => {
    loadApplications()
  }, [loadApplications])

  // Auto-refresh after sync completes (poll for sync status)
  useEffect(() => {
    if (isGuest) return

    const checkSyncStatus = async () => {
      try {
        const status = await gmailService.getStatus()
        // If sync just completed, reload applications
        if (status.connected && !status.syncJobId) {
          // Small delay to ensure backend has processed
          setTimeout(() => {
            loadApplications()
          }, 1000)
        }
      } catch (err) {
        // Ignore errors in status check
      }
    }

    // Poll every 5 seconds when on Applications page
    const interval = setInterval(checkSyncStatus, 5000)
    return () => clearInterval(interval)
  }, [isGuest, loadApplications])

  // Normalize category for display (backend returns uppercase)
  const normalizeCategory = (category) => {
    if (!category) return null
    const cat = category.toUpperCase()
    if (cat === 'ACCEPTED' || cat === 'OFFER') return 'OFFER_ACCEPTED'
    return cat
  }

  // Get category label
  const getCategoryLabel = (category) => {
    const normalized = normalizeCategory(category)
    return CATEGORY_LABELS[normalized] || category || 'Unknown'
  }

  // Filter applications
  const filtered = useMemo(() => {
    let list = applications

    // Search filter
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (a) =>
          (a.company_name || '').toLowerCase().includes(q) ||
          (a.role || '').toLowerCase().includes(q) ||
          (a.subject || '').toLowerCase().includes(q)
      )
    }

    // Status filter (match by label)
    if (statusFilter && statusFilter !== 'All Statuses') {
      list = list.filter((a) => {
        const normalized = normalizeCategory(a.category)
        const label = CATEGORY_LABELS[normalized]
        return label === statusFilter
      })
    }

    return list
  }, [applications, search, statusFilter])

  // Handle application click - open Gmail
  const handleApplicationClick = (app) => {
    if (app.gmail_web_url) {
      window.open(app.gmail_web_url, '_blank', 'noopener,noreferrer')
    } else if (app.gmail_message_id) {
      // Fallback: construct URL if web_url is missing
      const gmailUrl = `https://mail.google.com/mail/u/0/#inbox/${app.gmail_message_id}`
      window.open(gmailUrl, '_blank', 'noopener,noreferrer')
    } else {
      setError('Gmail link not available for this application')
    }
  }

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return '—'
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    } catch {
      return '—'
    }
  }

  if (isGuest) {
    return (
      <div className="applications-page-perfect">
        <div className="dashboard-header-section">
          <div className="dashboard-title-area">
            <h1 className="dashboard-main-title">Applications</h1>
            <p className="dashboard-subtitle">Track and manage your pipeline</p>
          </div>
        </div>
        <div className="content-card-perfect">
          <div className="export-guest-warning">
            <IconAlertCircle />
            <span>Applications are disabled in Guest Mode. Connect Gmail to view your applications.</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="applications-page-perfect">
      {/* Header Section */}
      <div className="dashboard-header-section">
        <div className="dashboard-title-area">
          <h1 className="dashboard-main-title">Applications</h1>
          <p className="dashboard-subtitle">Track and manage your pipeline</p>
        </div>
        <div className="dashboard-actions">
          <button
            type="button"
            className="dashboard-action-btn dashboard-action-btn-secondary"
            onClick={() => window.location.href = '/export'}
          >
            <IconDownload />
            <span>Export</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="export-error">
          <IconAlertCircle />
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="error-close-btn">
            ×
          </button>
        </div>
      )}

      {/* Filters Card */}
      <div className="content-card-perfect filters-card-perfect">
        <div className="filters-content">
          <div className="filter-search-wrapper">
            <IconSearch className="filter-search-icon" />
            <input
              type="text"
              placeholder="Search company, role..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="filter-search-input"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
          >
            {CATEGORY_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <div className="filter-view-toggle">
            <button
              type="button"
              className={`view-toggle-btn ${viewMode === 'list' ? 'active' : ''}`}
              onClick={() => setViewMode('list')}
              aria-label="List view"
            >
              <IconList />
            </button>
            <button
              type="button"
              className={`view-toggle-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              aria-label="Grid view"
            >
              <IconGridSmall />
            </button>
          </div>
        </div>
      </div>

      {/* Applications Card */}
      <div className="content-card-perfect applications-card-perfect">
        <div className="content-card-header">
          <div className="content-card-title-group">
            <div className="content-card-icon">
              <IconBriefcase />
            </div>
            <div>
              <h2 className="content-card-title">All Applications</h2>
              <p className="content-card-subtitle">
                {loading ? 'Loading...' : `${filtered.length} of ${applications.length} applications`}
              </p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="applications-loading">
            <div className="upload-spinner" />
            <p>Loading applications...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="applications-empty-perfect">
            <div className="empty-icon-wrapper">
              <IconBriefcase />
            </div>
            <p className="empty-title">No records found</p>
            <p className="empty-text">
              {applications.length === 0
                ? 'No applications found. Sync your Gmail to see your applications.'
                : 'Try adjusting your filters or search query to find what you\'re looking for.'}
            </p>
          </div>
        ) : (
          <div className={`applications-list-perfect applications-list-${viewMode}`}>
            {filtered.map((app) => {
              const category = normalizeCategory(app.category)
              const categoryLabel = getCategoryLabel(app.category)

              return (
                <div
                  key={app.id}
                  className="application-item-perfect application-item-clickable"
                  onClick={() => handleApplicationClick(app)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      handleApplicationClick(app)
                    }
                  }}
                  title="Click to open in Gmail"
                >
                  <div className="application-item-icon">
                    <IconBriefcase />
                  </div>
                  <div className="application-item-info">
                    <div className="application-company">{app.company_name || 'Unknown Company'}</div>
                    <div className="application-meta">
                      {app.role && <span className="application-role">{app.role}</span>}
                      {app.role && app.received_at && <span className="application-separator">•</span>}
                      {app.received_at && (
                        <span className="application-date">{formatDate(app.received_at)}</span>
                      )}
                      <span className="application-source">Source: Gmail</span>
                    </div>
                  </div>
                  <div className="application-item-right">
                    <div className={`activity-status activity-status-${(category || 'UNKNOWN').toLowerCase()}`}>
                      {categoryLabel}
                    </div>
                    <IconExternalLink className="application-gmail-link-icon" />
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Footer - No pagination, show total count */}
        {!loading && filtered.length > 0 && (
          <div className="applications-pagination-perfect">
            <span className="pagination-text">
              Showing all {filtered.length} application{filtered.length !== 1 ? 's' : ''}
              {filtered.length < applications.length && ` (filtered from ${applications.length} total)`}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

