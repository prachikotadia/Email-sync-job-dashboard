import { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FixedSizeList } from 'react-window'
import { useAuth } from '../context/AuthContext'
import { gmailService } from '../services/gmailService'
import { resumeService } from '../services/resumeService'
import ApplicationRow from '../components/ApplicationRow'
import { IconDownload, IconList, IconGridSmall, IconBriefcase, IconSearch, IconAlertCircle, IconExternalLink, IconCopy, IconFilter, IconChevronDown, IconFile, IconFileText } from '../components/icons'
import { toast } from '../utils/toast'
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
  const [searchParams, setSearchParams] = useSearchParams()
  
  // URL-driven state: tab and company filter
  const activeTab = searchParams.get('tab') || 'all' // 'all' | 'company'
  const companyFilter = searchParams.get('company') || null
  
  // Tab state preservation - separate data per tab to prevent unnecessary refetch
  const [applicationsAllTab, setApplicationsAllTab] = useState([]) // Data for "all" tab
  const [companiesTab, setCompaniesTab] = useState([]) // Data for "company" tab
  const [applicationsLoaded, setApplicationsLoaded] = useState(false) // Track if "all" tab data is loaded
  const [companiesLoaded, setCompaniesLoaded] = useState(false) // Track if "company" tab data is loaded
  
  // Current tab's data (derived from active tab)
  const applications = activeTab === 'all' ? applicationsAllTab : []
  const companies = activeTab === 'company' ? companiesTab : []
  
  // Scroll position preservation per tab
  const scrollPositionAllTab = useRef(0)
  const scrollPositionCompanyTab = useRef(0)
  const listRef = useRef(null) // Ref for FixedSizeList
  const outerListRef = useRef(null) // Ref for outer container (for scroll tracking)
  
  const [loading, setLoading] = useState(true)
  const [companiesLoading, setCompaniesLoading] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('All Statuses')
  const [selectedStatuses, setSelectedStatuses] = useState([]) // Multi-select status
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false)
  const [viewMode, setViewMode] = useState('list') // 'list' | 'grid'
  const [usingSearch, setUsingSearch] = useState(false) // Track if using API search or full list
  const [totalResults, setTotalResults] = useState(0)
  const [copySuccess, setCopySuccess] = useState(null) // For copy link feedback
  const [nextCursor, setNextCursor] = useState(null) // Cursor for pagination
  const [hasMore, setHasMore] = useState(false) // Track if more data available
  
  // Resume linking state - map of application_id -> { resume_id, resume_name }
  const [applicationResumes, setApplicationResumes] = useState({}) // { [appId]: { resume_id, resume_name } }
  // Shared resumes list (loaded once, passed to all ResumeSelector components)
  const [allResumes, setAllResumes] = useState([])
  const [resumesLoading, setResumesLoading] = useState(false)
  const resumesLoadedRef = useRef(false)
  
  // Debounce timer ref
  const searchTimeoutRef = useRef(null)
  // Cancel token ref for in-flight requests
  const searchAbortControllerRef = useRef(null)
  // Guard ref to prevent concurrent resume loading
  const loadingResumesRef = useRef(false)
  // Ref to store the latest loadApplicationResumes function to avoid dependency issues
  const loadApplicationResumesRef = useRef(null)
  
  // Load all resumes once (shared across all ResumeSelector components)
  const loadAllResumes = useCallback(async () => {
    if (isGuest || resumesLoadedRef.current || resumesLoading) return
    
    setResumesLoading(true)
    try {
      const data = await resumeService.listResumes()
      setAllResumes(data)
      resumesLoadedRef.current = true
    } catch (err) {
      console.error('Error loading resumes:', err)
      // Don't show error toast - resume loading is non-critical
    } finally {
      setResumesLoading(false)
    }
  }, [isGuest, resumesLoading])
  
  // Load resumes once on mount
  useEffect(() => {
    if (!isGuest && !resumesLoadedRef.current) {
      loadAllResumes()
    }
  }, [isGuest, loadAllResumes])
  
  // Load resume data for applications (MUST be defined before loadApplications to avoid TDZ)
  const loadApplicationResumes = useCallback(async (applicationIds) => {
    if (isGuest || !applicationIds || applicationIds.length === 0) return
    
    // Guard against concurrent calls
    if (loadingResumesRef.current) {
      return
    }
    
    loadingResumesRef.current = true
    
    try {
      // Batch load resumes for all applications (limit to 20 at a time to avoid overwhelming)
      const batchSize = 20
      const batches = []
      for (let i = 0; i < applicationIds.length; i += batchSize) {
        batches.push(applicationIds.slice(i, i + batchSize))
      }
      
      for (const batch of batches) {
        const resumePromises = batch.map(async (appId) => {
          try {
            const result = await resumeService.getApplicationResume(appId)
            return { appId, resume: result.resume }
          } catch (err) {
            // 404 is okay - no resume linked
            return { appId, resume: null }
          }
        })
        
        const results = await Promise.all(resumePromises)
        const resumeMap = {}
        results.forEach(({ appId, resume }) => {
          if (resume) {
            resumeMap[appId] = { resume_id: resume.id, resume_name: resume.file_name }
          }
        })
        
        setApplicationResumes(prev => ({ ...prev, ...resumeMap }))
      }
    } catch (err) {
      console.error('Error loading application resumes:', err)
      // Don't show error toast - resume loading is non-critical
    } finally {
      loadingResumesRef.current = false
    }
  }, [isGuest])
  
  // Store the latest function in a ref to avoid dependency issues
  useEffect(() => {
    loadApplicationResumesRef.current = loadApplicationResumes
  }, [loadApplicationResumes])
  
  // Update URL when tab changes (preserve other params like company)
  const setActiveTab = useCallback((tab) => {
    const newParams = new URLSearchParams(searchParams)
    if (tab === 'all') {
      newParams.set('tab', 'all')
      // Clear company filter when switching to "all" tab
      newParams.delete('company')
    } else {
      newParams.set('tab', 'company')
    }
    setSearchParams(newParams, { replace: true })
  }, [searchParams, setSearchParams])
  
  // Handle company filter change
  const setCompanyFilter = useCallback((companyName) => {
    const newParams = new URLSearchParams(searchParams)
    if (companyName) {
      newParams.set('company', companyName)
      newParams.set('tab', 'all') // Switch to "all" tab when filtering by company
    } else {
      newParams.delete('company')
    }
    setSearchParams(newParams, { replace: true })
  }, [searchParams, setSearchParams])

  // Load applications from backend (full list, no search)
  // Only loads if not already loaded (tab state preservation)
  const loadApplications = useCallback(async (companyName = null, forceRefresh = false) => {
    if (isGuest) {
      setApplicationsAllTab([])
      setLoading(false)
      setApplicationsLoaded(false)
      return
    }

    // Tab state preservation: only load if not already loaded or force refresh
    if (!forceRefresh && applicationsLoaded && applicationsAllTab.length > 0 && !companyName) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const filters = companyName ? { company: companyName } : {}
      const res = await gmailService.getApplications(filters)
      const apps = res.applications || []
      setApplicationsAllTab(apps)
      setUsingSearch(false)
      setApplicationsLoaded(true)
      
      // Load resume data for all applications (use ref to avoid dependency)
      if (!isGuest && apps.length > 0 && loadApplicationResumesRef.current) {
        loadApplicationResumesRef.current(apps.map(app => app.id))
      }
    } catch (err) {
      console.error('Error loading applications:', err)
      setError(err.message || 'Failed to load applications')
      setApplicationsAllTab([])
    } finally {
      setLoading(false)
    }
  }, [isGuest, applicationsLoaded, applicationsAllTab.length])

  // Load companies grouped by company name
  // Only loads if not already loaded (tab state preservation)
  const loadCompanies = useCallback(async (forceRefresh = false) => {
    if (isGuest) {
      setCompaniesTab([])
      setCompaniesLoading(false)
      setCompaniesLoaded(false)
      return
    }

    // Tab state preservation: only load if not already loaded or force refresh
    if (!forceRefresh && companiesLoaded && companiesTab.length > 0) {
      setCompaniesLoading(false)
      return
    }

    try {
      setCompaniesLoading(true)
      setError(null)
      const res = await gmailService.getApplicationsGroupedByCompany()
      setCompaniesTab(res.companies || [])
      setCompaniesLoaded(true)
    } catch (err) {
      console.error('Error loading companies:', err)
      setError(err.message || 'Failed to load companies')
      setCompaniesTab([])
    } finally {
      setCompaniesLoading(false)
    }
  }, [isGuest, companiesLoaded, companiesTab.length])

  // Debounced unified search function (300ms delay)
  const performSearch = useCallback(async (query, statusFilters = [], dateFromFilter = '', dateToFilter = '') => {
    if (isGuest) return
    
    // Cancel any in-flight search request
    if (searchAbortControllerRef.current) {
      searchAbortControllerRef.current.abort()
    }
    
    // Create new abort controller for this search
    const abortController = new AbortController()
    searchAbortControllerRef.current = abortController
    
    const hasActiveFilters = (query && query.trim()) || (statusFilters && statusFilters.length > 0) || dateFromFilter || dateToFilter
    
    if (!hasActiveFilters) {
      // No filters - load all applications
      setUsingSearch(false)
      await loadApplications(companyFilter)
      return
    }
    
    try {
      setSearchLoading(true)
      setError(null)
      
      // Use unified search endpoint with all filters
      const searchResult = await gmailService.unifiedSearch({
        q: query?.trim() || null,
        status: statusFilters.length > 0 ? statusFilters : null,
        company: companyFilter || null,
        date_from: dateFromFilter || null,
        date_to: dateToFilter || null,
        page: 1,
        page_size: 100, // Large page size for virtualization
        sort_by: 'last_activity_at',
        sort_order: 'desc'
      })
      
      // Check if request was aborted
      if (abortController.signal.aborted) {
        return
      }
      
      const newApplications = searchResult.data || []
      setApplicationsAllTab(newApplications)
      setTotalResults(searchResult.pagination?.total || 0)
      setNextCursor(searchResult.pagination?.next_cursor || null)
      setHasMore(searchResult.pagination?.next_cursor !== null)
      setUsingSearch(true)
    } catch (err) {
      // Ignore abort errors
      if (err.name === 'AbortError' || abortController.signal.aborted) {
        return
      }
      
      console.error('Error searching applications:', err)
      setError(err.message || 'Search failed')
      setApplicationsAllTab([])
    } finally {
      if (!abortController.signal.aborted) {
        setSearchLoading(false)
      }
    }
  }, [isGuest, loadApplications, companyFilter])

  // Handle search input change with debouncing
  const handleSearchChange = useCallback((value) => {
    setSearch(value)
    
    // Clear existing timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }
    
    // Cancel in-flight request
    if (searchAbortControllerRef.current) {
      searchAbortControllerRef.current.abort()
    }
    
    // Set new timeout for debounced search (300ms)
    searchTimeoutRef.current = setTimeout(() => {
      performSearch(value, selectedStatuses, dateFrom, dateTo)
    }, 300)
  }, [performSearch, selectedStatuses, dateFrom, dateTo])

  // Effect to sync filters to URL params
  useEffect(() => {
    const params = new URLSearchParams(searchParams)
    if (selectedStatuses.length > 0) {
      params.set('status', selectedStatuses.join(','))
    } else {
      params.delete('status')
    }
    if (dateFrom) params.set('date_from', dateFrom)
    else params.delete('date_from')
    if (dateTo) params.set('date_to', dateTo)
    else params.delete('date_to')
    // Note: search is already synced via handleSearchChange
    setSearchParams(params, { replace: true })
  }, [selectedStatuses, dateFrom, dateTo, searchParams, setSearchParams])

  // Load filters from URL on mount
  useEffect(() => {
    const statusParam = searchParams.get('status')
    if (statusParam) {
      setSelectedStatuses(statusParam.split(',').filter(Boolean))
    }
    const dateFromParam = searchParams.get('date_from')
    if (dateFromParam) setDateFrom(dateFromParam)
    const dateToParam = searchParams.get('date_to')
    if (dateToParam) setDateTo(dateToParam)
  }, []) // Only on mount

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
      if (searchAbortControllerRef.current) {
        searchAbortControllerRef.current.abort()
      }
    }
  }, [])

  // Load data based on active tab - ONLY on tab switch or initial mount
  // Tab state preservation: don't refetch if data already loaded
  useEffect(() => {
    if (activeTab === 'company') {
      // Load companies list for "By Company" tab (only if not loaded)
      loadCompanies()
    } else {
      // Load applications (filtered by company if company param is present)
      loadApplications(companyFilter)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, companyFilter]) // Only depend on activeTab and companyFilter to prevent infinite loops
  
  // Restore scroll position when switching tabs
  useEffect(() => {
    if (listRef.current && activeTab === 'all' && applicationsAllTab.length > 0) {
      // Restore scroll position for "all" tab
      setTimeout(() => {
        if (listRef.current && scrollPositionAllTab.current > 0) {
          listRef.current.scrollToItem(Math.floor(scrollPositionAllTab.current / 100), 'start')
        }
      }, 100)
    }
  }, [activeTab, applicationsAllTab.length])

  // Auto-refresh after sync completes (listen for sync completion)
  useEffect(() => {
    if (isGuest) return

    let syncCheckInterval = null
    let lastSyncJobId = null

    const checkSyncStatus = async () => {
      try {
        const status = await gmailService.getStatus()
        const currentSyncJobId = status.syncJobId

        // If sync was running and now completed
        if (lastSyncJobId && !currentSyncJobId) {
          // Sync just completed - reload applications (clear search if active)
          setTimeout(() => {
            if (!search.trim()) {
              loadApplications()
            }
          }, 1000)
        }

        lastSyncJobId = currentSyncJobId

        // If sync is running, poll its status
        if (currentSyncJobId) {
          try {
            const syncStatus = await gmailService.getSyncStatus(currentSyncJobId)
            if (syncStatus.status === 'completed') {
              // Sync completed - reload applications
              setTimeout(() => {
                if (!search.trim()) {
                  loadApplications()
                }
              }, 1000)
              if (syncCheckInterval) {
                clearInterval(syncCheckInterval)
                syncCheckInterval = null
              }
            } else if (syncStatus.status === 'failed') {
              setError(syncStatus.errors?.[0] || 'Sync failed')
              if (syncCheckInterval) {
                clearInterval(syncCheckInterval)
                syncCheckInterval = null
              }
            }
          } catch (err) {
            // Ignore errors in sync status check
          }
        }
      } catch (err) {
        // Ignore errors in status check
      }
    }

    // NO POLLING - SSE handles progress updates
    // Only check once on mount if needed
    checkSyncStatus()

    return () => {
      // Cleanup handled by SSE hook
    }
  }, [isGuest, loadApplications, search])

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

  // Load more applications with cursor pagination
  const loadMoreApplications = useCallback(async () => {
    if (!nextCursor || isGuest || loading || searchLoading) return
    
    try {
      setSearchLoading(true)
      const result = await gmailService.unifiedSearch({
        q: search?.trim() || null,
        status: selectedStatuses.length > 0 ? selectedStatuses : null,
        company: companyFilter || null,
        date_from: dateFrom || null,
        date_to: dateTo || null,
        cursor: nextCursor,
        limit: 50,
        sort_by: 'last_activity_at',
        sort_order: 'desc'
      })
      
      const newApplications = result.data || []
      setApplicationsAllTab(prev => [...prev, ...newApplications])
      setNextCursor(result.pagination?.next_cursor || null)
      setHasMore(result.pagination?.next_cursor !== null)
    } catch (err) {
      console.error('Error loading more applications:', err)
    } finally {
      setSearchLoading(false)
    }
  }, [nextCursor, isGuest, loading, searchLoading, search, selectedStatuses, companyFilter, dateFrom, dateTo])

  // Filter applications - when using unified search, filtering is done by backend
  // Only apply client-side filtering if not using search API
  const filtered = useMemo(() => {
    if (usingSearch) {
      // Backend already filtered, return as-is
      return applicationsAllTab
    }
    
    let list = applicationsAllTab

    // Apply multi-select status filter if not using search
    if (selectedStatuses.length > 0) {
      list = list.filter((a) => {
        const normalized = normalizeCategory(a.category)
        return selectedStatuses.includes(normalized)
      })
    }

    return list
  }, [applicationsAllTab, selectedStatuses, usingSearch])

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

  // Handle resume change for an application
  const handleResumeChange = useCallback((applicationId, resumeId) => {
    // Optimistic update - ResumeSelector already handles the API call
    // This just updates local state for immediate UI feedback
    setApplicationResumes(prev => {
      // The ResumeSelector will fetch resume details, but we update optimistically
      return {
        ...prev,
        [applicationId]: resumeId ? { resume_id: resumeId, resume_name: 'Loading...' } : null
      }
    })
  }, [])

  // Copy Gmail deep link to clipboard
  const handleCopyLink = async (app, e) => {
    e.stopPropagation() // Prevent opening Gmail
    
    // Use gmail_deep_link (new) or fallback to gmail_web_url (legacy) or gmail_message_id
    let url = app.gmail_deep_link || app.gmail_web_url
    
    // If no URL but we have message ID, generate it (shouldn't happen, but fallback)
    if (!url && app.gmail_message_id) {
      url = `https://mail.google.com/mail/u/0/#all/${app.gmail_message_id}`
    }
    
    if (!url) {
      // No link available - show error toast
      toast.error('Email link unavailable - message ID missing')
      return
    }
    
    try {
      await navigator.clipboard.writeText(url)
      // Show success toast
      toast.success('Email link copied to clipboard')
      setCopySuccess(app.id)
      setTimeout(() => setCopySuccess(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
      const errorMsg = 'Failed to copy link to clipboard'
      toast.error(errorMsg)
      setError(errorMsg)
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

  // Format month for timeline (e.g., "January 2024")
  const formatMonth = (monthKey) => {
    try {
      const [year, month] = monthKey.split('-')
      const date = new Date(parseInt(year), parseInt(month) - 1, 1)
      return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    } catch {
      return monthKey
    }
  }

  // Group applications by month for timeline view
  const groupByMonth = useCallback((apps) => {
    const grouped = {}
    apps.forEach(app => {
      if (!app.received_at) return
      try {
        const date = new Date(app.received_at)
        const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
        if (!grouped[monthKey]) {
          grouped[monthKey] = []
        }
        grouped[monthKey].push(app)
      } catch {
        // Skip invalid dates
      }
    })
    // Sort each month's applications by date (newest first)
    Object.keys(grouped).forEach(key => {
      grouped[key].sort((a, b) => {
        const dateA = new Date(a.received_at || 0)
        const dateB = new Date(b.received_at || 0)
        return dateB - dateA
      })
    })
    return grouped
  }, [])

  // Note: Timeline uses filtered applications directly, no separate state needed

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

  const isLoading = loading || searchLoading

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

      {/* Tabs - Always visible at top */}
      <div 
        className="content-card-perfect" 
        style={{ 
          padding: '0', 
          marginBottom: '1.5rem',
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid #334155',
          borderRadius: '12px',
          overflow: 'hidden',
        }}
      >
        <div 
          style={{ 
            display: 'flex', 
            borderBottom: '2px solid #1e293b',
            background: 'rgba(255, 255, 255, 0.01)',
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab('all')}
            className={`tab-button ${activeTab === 'all' ? 'active' : ''}`}
            style={{
              flex: 1,
              padding: '1.125rem 1.5rem',
              background: activeTab === 'all' 
                ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(99, 102, 241, 0.08) 100%)' 
                : 'transparent',
              border: 'none',
              borderBottom: activeTab === 'all' ? '3px solid #6366f1' : '3px solid transparent',
              color: activeTab === 'all' ? '#a5b4fc' : '#94a3b8',
              cursor: 'pointer',
              fontSize: '1rem',
              fontWeight: activeTab === 'all' ? '700' : '500',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              position: 'relative',
              letterSpacing: '-0.01em',
            }}
            onMouseEnter={(e) => {
              if (activeTab !== 'all') {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'
                e.currentTarget.style.color = '#cbd5e1'
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'all') {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = '#94a3b8'
              }
            }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>📋</span>
              All Applications
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('company')}
            className={`tab-button ${activeTab === 'company' ? 'active' : ''}`}
            style={{
              flex: 1,
              padding: '1.125rem 1.5rem',
              background: activeTab === 'company' 
                ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(99, 102, 241, 0.08) 100%)' 
                : 'transparent',
              border: 'none',
              borderBottom: activeTab === 'company' ? '3px solid #6366f1' : '3px solid transparent',
              color: activeTab === 'company' ? '#a5b4fc' : '#94a3b8',
              cursor: 'pointer',
              fontSize: '1rem',
              fontWeight: activeTab === 'company' ? '700' : '500',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              position: 'relative',
              letterSpacing: '-0.01em',
            }}
            onMouseEnter={(e) => {
              if (activeTab !== 'company') {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'
                e.currentTarget.style.color = '#cbd5e1'
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'company') {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = '#94a3b8'
              }
            }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>🏢</span>
              By Company
            </span>
          </button>
        </div>
      </div>

      {/* Filters Card - Only show in "All Applications" tab or when company filter is active */}
      {(activeTab === 'all' || companyFilter) && (
      <div className="content-card-perfect filters-card-perfect">
        <div className="filters-content">
          <div className="filter-search-wrapper">
            <IconSearch className="filter-search-icon" />
            <input
              type="text"
                placeholder="Search company, role, application, or status…"
              value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
              className="filter-search-input"
                disabled={isLoading}
            />
              {searchLoading && (
                <div className="search-loading-spinner" style={{ marginLeft: '8px' }}>
                  <div className="upload-spinner" style={{ width: '16px', height: '16px' }} />
                </div>
              )}
          </div>
            <button
              type="button"
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            className="filter-select"
              disabled={isLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                cursor: 'pointer',
              }}
            >
              <IconFilter />
              <span>Advanced Filters</span>
              <IconChevronDown style={{
                transform: showAdvancedFilters ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s',
              }} />
            </button>
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
          
          {/* Advanced Filters Panel */}
          {showAdvancedFilters && (
            <div style={{
              marginTop: '1rem',
              padding: '1rem',
              background: '#1e293b',
              borderRadius: '0.5rem',
              border: '1px solid #334155',
            }}>
              {/* Multi-select Status Filter */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: '500', color: '#e2e8f0' }}>
                  Status (Select multiple)
                </label>
                <div style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                }}>
                  {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                    <label
                      key={key}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        cursor: 'pointer',
                        fontSize: '0.875rem',
                        color: '#cbd5e1',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedStatuses.includes(key)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedStatuses([...selectedStatuses, key])
                          } else {
                            setSelectedStatuses(selectedStatuses.filter(s => s !== key))
                          }
                          // Trigger search with new filters
                          setTimeout(() => {
                            performSearch(search, e.target.checked ? [...selectedStatuses, key] : selectedStatuses.filter(s => s !== key), dateFrom, dateTo)
                          }, 100)
                        }}
                        disabled={isLoading}
                        style={{ cursor: 'pointer' }}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </div>

              {/* Date Range Filter */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: '500', color: '#e2e8f0' }}>
                  Date Range
                </label>
                <div style={{
                  display: 'flex',
                  gap: '1rem',
                  alignItems: 'center',
                }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                      From
                    </label>
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={(e) => {
                        setDateFrom(e.target.value)
                        setTimeout(() => {
                          performSearch(search, selectedStatuses, e.target.value, dateTo)
                        }, 100)
                      }}
                      className="filter-search-input"
                      disabled={isLoading}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                      To
                    </label>
                    <input
                      type="date"
                      value={dateTo}
                      onChange={(e) => {
                        setDateTo(e.target.value)
                        setTimeout(() => {
                          performSearch(search, selectedStatuses, dateFrom, e.target.value)
                        }, 100)
                      }}
                      className="filter-search-input"
                      disabled={isLoading}
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              </div>

              {/* Clear Filters Button */}
              {(selectedStatuses.length > 0 || dateFrom || dateTo) && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedStatuses([])
                    setDateFrom('')
                    setDateTo('')
                    setTimeout(() => {
                      performSearch(search, [], '', '')
                    }, 100)
                  }}
                  style={{
                    padding: '0.5rem 1rem',
                    background: '#334155',
                    border: '1px solid #475569',
                    borderRadius: '0.375rem',
                    color: '#e2e8f0',
                    cursor: 'pointer',
                    fontSize: '0.875rem',
                  }}
                >
                  Clear Filters
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Content: Show companies list or applications list based on active tab */}
      {activeTab === 'company' ? (
        /* By Company Tab - Company Cards */
        <div className="content-card-perfect applications-card-perfect">
          <div className="content-card-header">
            <div className="content-card-title-group">
              <div className="content-card-icon">
                <IconBriefcase />
              </div>
              <div>
                <h2 className="content-card-title">By Company</h2>
                <p className="content-card-subtitle">
                  {companiesLoading ? 'Loading...' : `${companies.length} companies`}
                </p>
          </div>
        </div>
      </div>

          {companiesLoading ? (
            // Skeleton loader for companies
            <div style={{ padding: '1rem' }}>
              {[...Array(8)].map((_, i) => (
                <div
                  key={i}
                  style={{
                    height: '100px',
                    marginBottom: '0.5rem',
                    background: '#1e293b',
                    borderRadius: '0.5rem',
                    border: '1px solid #334155',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '1rem',
                    gap: '1rem',
                    animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                  }}
                >
                  <div style={{
                    width: '48px',
                    height: '48px',
                    background: '#334155',
                    borderRadius: '0.5rem',
                    flexShrink: 0,
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{
                      height: '20px',
                      width: '150px',
                      background: '#334155',
                      borderRadius: '0.25rem',
                      marginBottom: '0.5rem',
                    }} />
                    <div style={{
                      height: '16px',
                      width: '250px',
                      background: '#334155',
                      borderRadius: '0.25rem',
                      opacity: 0.7,
                    }} />
                  </div>
                </div>
              ))}
            </div>
          ) : companies.length === 0 ? (
            <div className="applications-empty-perfect">
              <div className="empty-icon-wrapper">
                <IconBriefcase />
              </div>
              <p className="empty-title">No companies found</p>
              <p className="empty-text">Sync your Gmail to see your applications grouped by company.</p>
            </div>
          ) : (
            <div className="applications-list-perfect applications-list-list">
              {companies.map((company) => {
                const statusEntries = Object.entries(company.statuses || {}).filter(([_, count]) => count > 0)
                const latestDate = company.latest_applied_at ? formatDate(company.latest_applied_at) : '—'

                return (
                  <div
                    key={company.company_name}
                    className="application-item-perfect application-item-clickable"
                    onClick={() => setCompanyFilter(company.company_name)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setCompanyFilter(company.company_name)
                      }
                    }}
                    style={{ cursor: 'pointer' }}
                    title="Click to view applications for this company"
                  >
                    <div className="application-item-icon">
                      <IconBriefcase />
                    </div>
                    <div className="application-item-info" style={{ flex: 1 }}>
                      <div className="application-company">{company.company_name}</div>
                      <div className="application-meta" style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
                        <span style={{ fontWeight: '600' }}>{company.total_applications} Application{company.total_applications !== 1 ? 's' : ''}</span>
                        {statusEntries.length > 0 && (
                          <>
                            <span className="application-separator">•</span>
                            <span>
                              {statusEntries.map(([status, count], idx) => (
                                <span key={status}>
                                  {idx > 0 && ', '}
                                  {CATEGORY_LABELS[status] || status}: {count}
                                </span>
                              ))}
                            </span>
                          </>
                        )}
                        <span className="application-separator">•</span>
                        <span>Last activity: {latestDate}</span>
                      </div>
                    </div>
                    <div className="application-item-right">
                      <span style={{ color: '#3b82f6', fontSize: '0.875rem', fontWeight: '500' }}>→ Click to view</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        /* All Applications Tab */
      <div className="content-card-perfect applications-card-perfect">
        <div className="content-card-header">
          <div className="content-card-title-group">
            <div className="content-card-icon">
              <IconBriefcase />
            </div>
            <div>
              <h2 className="content-card-title">{companyFilter ? `Applications - ${companyFilter}` : 'All Applications'}</h2>
              <p className="content-card-subtitle">
                {isLoading ? 'Loading...' : `${filtered.length}${usingSearch ? ' search results' : ` of ${applicationsAllTab.length} applications`}`}
              </p>
            </div>
          </div>
        </div>

        {isLoading && !usingSearch ? (
          // Skeleton loader instead of spinner
          <div style={{ padding: '1rem' }}>
            {[...Array(10)].map((_, i) => (
              <div
                key={i}
                style={{
                  height: '100px',
                  marginBottom: '0.5rem',
                  background: '#1e293b',
                  borderRadius: '0.5rem',
                  border: '1px solid #334155',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '1rem',
                  gap: '1rem',
                  animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                }}
              >
                <div style={{
                  width: '48px',
                  height: '48px',
                  background: '#334155',
                  borderRadius: '0.5rem',
                  flexShrink: 0,
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{
                    height: '20px',
                    width: '200px',
                    background: '#334155',
                    borderRadius: '0.25rem',
                    marginBottom: '0.5rem',
                  }} />
                  <div style={{
                    height: '16px',
                    width: '300px',
                    background: '#334155',
                    borderRadius: '0.25rem',
                    opacity: 0.7,
                  }} />
                </div>
                <div style={{
                  width: '80px',
                  height: '24px',
                  background: '#334155',
                  borderRadius: '0.25rem',
                }} />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="applications-empty-perfect">
            <div className="empty-icon-wrapper">
              <IconBriefcase />
            </div>
            <p className="empty-title">No results found</p>
            <p className="empty-text">
              {search.trim()
                ? 'Try adjusting your search query or filters to find what you\'re looking for.'
                : 'No applications found. Sync your Gmail to see your applications.'}
            </p>
          </div>
        ) : (
          // ALWAYS use virtualized list for performance (REQUIRED for 10k+ applications)
          <div style={{ height: '600px', width: '100%', position: 'relative' }}>
            <FixedSizeList
              ref={listRef}
              height={600}
              itemCount={filtered.length}
              itemSize={140}
              width="100%"
              onScroll={({ scrollOffset }) => {
                // Store scroll position per tab
                if (activeTab === 'all') {
                  scrollPositionAllTab.current = scrollOffset
                } else if (activeTab === 'company') {
                  scrollPositionCompanyTab.current = scrollOffset
                }
              }}
              onItemsRendered={({ visibleStartIndex, visibleStopIndex }) => {
                // Cursor pagination: Load more when scrolling near end
                if (!usingSearch && hasMore && visibleStopIndex >= filtered.length - 5) {
                  loadMoreApplications()
                }
              }}
            >
              {({ index, style }) => {
                const app = filtered[index]
                return (
                  <ApplicationRow
                    key={app.id}
                    app={app}
                    style={style}
                    onApplicationClick={handleApplicationClick}
                    onCopyLink={handleCopyLink}
                    copySuccess={copySuccess}
                    applicationResume={applicationResumes[app.id]}
                    allResumes={allResumes}
                    onResumeChange={handleResumeChange}
                    onResumesChange={setAllResumes}
                    isGuest={isGuest}
                  />
                )
              }}
            </FixedSizeList>
          </div>
        )}

        {/* Footer - Show search info */}
        {!isLoading && filtered.length > 0 && (
          <div className="applications-pagination-perfect">
            <span className="pagination-text">
              {usingSearch ? (
                `Showing ${filtered.length} search result${filtered.length !== 1 ? 's' : ''}`
              ) : (
                `Showing all ${filtered.length} application${filtered.length !== 1 ? 's' : ''}`
              )}
            </span>
          </div>
        )}
      </div>
      )}
      
      {/* Company Timeline View - Show when filtering by company */}
      {companyFilter && filtered.length > 0 && (
        <div className="content-card-perfect" style={{ marginTop: '1.5rem' }}>
          <div className="content-card-header">
            <div className="content-card-title-group">
              <div className="content-card-icon">
                <IconBriefcase />
              </div>
              <div>
                <h2 className="content-card-title">Timeline - {companyFilter}</h2>
                <p className="content-card-subtitle">
                  {filtered.length} application{filtered.length !== 1 ? 's' : ''} grouped by month
                </p>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '1rem' }}>
            {Object.entries(groupByMonth(filtered))
              .sort((a, b) => b[0].localeCompare(a[0])) // Newest months first
              .map(([monthKey, monthApps]) => (
                <div key={monthKey} style={{ marginBottom: '2rem' }}>
                  <h3 style={{
                    fontSize: '1rem',
                    fontWeight: '600',
                    color: '#e2e8f0',
                    marginBottom: '1rem',
                    paddingBottom: '0.5rem',
                    borderBottom: '1px solid #334155',
                  }}>
                    {formatMonth(monthKey)}
                  </h3>
                  <div className="applications-list-perfect applications-list-list">
                    {monthApps.map((app) => {
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
                            <div className="application-company">{app.role || 'No Role'}</div>
                            <div className="application-meta">
                              {app.received_at && (
                                <span className="application-date">{formatDate(app.received_at)}</span>
                              )}
                              {app.subject && (
                                <>
                                  <span className="application-separator">•</span>
                                  <span className="application-role" style={{ fontSize: '0.875rem', color: '#94a3b8' }}>
                                    {app.subject.length > 60 ? app.subject.substring(0, 60) + '...' : app.subject}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                          <div className="application-item-right">
                            <div className={`activity-status activity-status-${(category || 'UNKNOWN').toLowerCase()}`}>
                              {categoryLabel}
                            </div>
                            <button
                              type="button"
                              onClick={(e) => handleCopyLink(app, e)}
                              className="copy-link-btn"
                              title={copySuccess === app.id ? 'Copied!' : 'Copy email link'}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                padding: '0.25rem',
                                color: copySuccess === app.id ? '#10b981' : '#94a3b8',
                                transition: 'color 0.2s',
                              }}
                            >
                              <IconCopy />
                            </button>
                            <IconExternalLink className="application-gmail-link-icon" />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Show back button when filtering by company */}
      {companyFilter && (
        <div style={{ marginTop: '1rem', textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => setCompanyFilter(null)}
            style={{
              padding: '0.5rem 1rem',
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '0.375rem',
              color: '#e2e8f0',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            ← Back to All Applications
          </button>
        </div>
      )}
    </div>
  )
}
