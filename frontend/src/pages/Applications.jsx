import { useEffect, useState, useMemo } from 'react'
import { useAuth } from '../context/AuthContext'
import { gmailService } from '../services/gmailService'
import { MOCK_APPLICATIONS } from '../mock/applications.mock'
import { IconDownload, IconList, IconGridSmall } from '../components/icons'
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
    <div className="applications-page">
      <div className="applications-header">
        <div>
          <h1>Applications</h1>
          <p className="applications-subtitle">Track and manage your pipeline</p>
        </div>
        <div className="applications-header-actions">
          <button type="button" className="applications-btn applications-btn-export">
            <IconDownload />
            <span>Export</span>
          </button>
          <button type="button" className="applications-btn applications-btn-primary">
            Add Entry
          </button>
        </div>
      </div>

      <div className="applications-filters">
        <input
          type="text"
          placeholder="Search company, role..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          className="applications-search"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="applications-status-select"
        >
          {statuses.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="applications-body">
        <div className="applications-view-toggle">
          <button
            type="button"
            className={viewMode === 'list' ? 'active' : ''}
            onClick={() => setViewMode('list')}
            aria-label="List view"
          >
            <IconList />
          </button>
          <button
            type="button"
            className={viewMode === 'grid' ? 'active' : ''}
            onClick={() => setViewMode('grid')}
            aria-label="Grid view"
          >
            <IconGridSmall />
          </button>
        </div>

        {pageItems.length === 0 ? (
          <div className="applications-empty">
            <div className="applications-empty-icon" />
            <p className="applications-empty-title">No records found</p>
            <p className="applications-empty-text">
              Try adjusting your filters or search query to find what you&apos;re looking for.
            </p>
          </div>
        ) : (
          <div className={`applications-list applications-list-${viewMode}`}>
            {pageItems.map((app, i) => (
              <div key={app.id || i} className="application-row">
                <div className="application-row-main">
                  <span className="application-row-company">{app.company || 'Unknown'}</span>
                  <span className="application-row-role">{app.role || '—'}</span>
                </div>
                <span className={`status-badge status-${(app.status || '').toLowerCase()}`}>
                  {app.status || '—'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="applications-footer">
        <span className="applications-pagination-text">
          Showing {total === 0 ? 0 : start + 1} to {end} of {total} results
        </span>
        <div className="applications-pagination">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            aria-label="Previous page"
          >
            &lt;
          </button>
          <button
            type="button"
            disabled={end >= total}
            onClick={() => setPage((p) => p + 1)}
            aria-label="Next page"
          >
            &gt;
          </button>
        </div>
      </div>
    </div>
  )
}
