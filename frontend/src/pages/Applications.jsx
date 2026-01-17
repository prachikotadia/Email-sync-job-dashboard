import { useEffect, useState, useMemo } from 'react'
import { useAuth } from '../context/AuthContext'
import { gmailService } from '../services/gmailService'
import { MOCK_APPLICATIONS } from '../mock/applications.mock'
import { IconDownload, IconList, IconGridSmall, IconBriefcase, IconSearch } from '../components/icons'
import '../styles/Applications.css'

const PAGE_SIZE = 10

export default function Applications() {
  const { isGuest } = useAuth()
  const [applications, setApplications] = useState(() => (isGuest ? MOCK_APPLICATIONS : []))
  const [loading, setLoading] = useState(() => !isGuest)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All Statuses')
  const [viewMode, setViewMode] = useState('list') // 'list' | 'grid'
  const [page, setPage] = useState(1)

  useEffect(() => {
    if (isGuest) {
      setLoading(false)
      return
    }
    let cancelled = false
    const load = async () => {
      try {
        const res = await gmailService.getApplications().catch(() => ({ applications: [], total: 0 }))
        if (!cancelled) {
          setApplications(res.applications || [])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [isGuest])

  const statuses = useMemo(() => {
    const s = new Set(applications.map((a) => a.status).filter(Boolean))
    return ['All Statuses', ...Array.from(s).sort()]
  }, [applications])

  const filtered = useMemo(() => {
    let list = applications
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (a) =>
          (a.company || '').toLowerCase().includes(q) ||
          (a.role || '').toLowerCase().includes(q)
      )
    }
    if (statusFilter && statusFilter !== 'All Statuses') {
      list = list.filter((a) => a.status === statusFilter)
    }
    return list
  }, [applications, search, statusFilter])

  const total = filtered.length
  const start = (page - 1) * PAGE_SIZE
  const end = Math.min(start + PAGE_SIZE, total)
  const pageItems = filtered.slice(start, end)

  if (loading) {
    return <div className="applications-loading">Loading applications...</div>
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
          <button type="button" className="dashboard-action-btn dashboard-action-btn-secondary">
            <IconDownload />
            <span>Export</span>
          </button>
          <button type="button" className="dashboard-action-btn">
            Add Entry
          </button>
        </div>
      </div>

      {/* Filters Card */}
      <div className="content-card-perfect filters-card-perfect">
        <div className="filters-content">
          <div className="filter-search-wrapper">
            <IconSearch className="filter-search-icon" />
            <input
              type="text"
              placeholder="Search company, role..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              className="filter-search-input"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            className="filter-select"
          >
            {statuses.map((s) => (
              <option key={s} value={s}>{s}</option>
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
              <p className="content-card-subtitle">{total} total applications</p>
            </div>
          </div>
        </div>

        {pageItems.length === 0 ? (
          <div className="applications-empty-perfect">
            <div className="empty-icon-wrapper">
              <IconBriefcase />
            </div>
            <p className="empty-title">No records found</p>
            <p className="empty-text">
              Try adjusting your filters or search query to find what you&apos;re looking for.
            </p>
          </div>
        ) : (
          <div className={`applications-list-perfect applications-list-${viewMode}`}>
            {pageItems.map((app, i) => (
              <div key={app.id || i} className="application-item-perfect">
                <div className="application-item-icon">
                  <IconBriefcase />
                </div>
                <div className="application-item-info">
                  <div className="application-company">{app.company || 'Unknown'}</div>
                  <div className="application-role">{app.role || '—'}</div>
                </div>
                <div className={`activity-status activity-status-${(app.status || '').toLowerCase()}`}>
                  {app.status || '—'}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        <div className="applications-pagination-perfect">
          <span className="pagination-text">
            Showing {total === 0 ? 0 : start + 1} to {end} of {total} results
          </span>
          <div className="pagination-controls">
            <button
              type="button"
              className="pagination-btn"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              aria-label="Previous page"
            >
              &lt;
            </button>
            <button
              type="button"
              className="pagination-btn"
              disabled={end >= total}
              onClick={() => setPage((p) => p + 1)}
              aria-label="Next page"
            >
              &gt;
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
