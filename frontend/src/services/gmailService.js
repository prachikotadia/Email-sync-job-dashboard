import apiClient from './apiClient'

export const gmailService = {
  /**
   * Get Gmail connection status
   * Returns 503 ONLY if service is down
   */
  async getStatus() {
    try {
      const response = await apiClient.get('/gmail/status')
      return response.data
    } catch (error) {
      if (error.response?.status === 503) {
        return { connected: false, error: 'Service unavailable' }
      }
      throw error
    }
  },

  /**
   * Start Gmail sync with optional time range
   * Returns sync_id and status
   * Contract: { "sync_id": "uuid", "status": "started" }
   * 
   * @param {Object} options - Sync options
   * @param {string} options.range - Time range: "3m" | "6m" | "12m" | "16m" | "full"
   * @param {number} options.months - Number of months (null for full history)
   */
  async startSync(options = {}) {
    try {
      const payload = {
        mode: options.range === 'full' ? 'full_history' : 'time_range',
        time_range_months: options.months || null
      }
      const response = await apiClient.post('/gmail/sync', payload)
      return response.data
    } catch (error) {
      if (error.response?.status === 409) {
        // Sync already running
        const message = error.response.data?.detail || 'Sync is already running'
        throw new Error(message)
      }
      throw error
    }
  },

  /**
   * Get sync status (polling endpoint)
   * Returns real-time counts from backend
   * Contract: { "status": "running|completed|failed", "emails_fetched": ..., "counts": {...}, ... }
   */
  async getSyncStatus(syncId) {
    try {
      const response = await apiClient.get('/gmail/sync/status', {
        params: { sync_id: syncId }
      })
      return response.data
    } catch (error) {
      throw error
    }
  },

  /**
   * Legacy method - redirects to getSyncStatus
   */
  async getSyncProgress(jobId) {
    return this.getSyncStatus(jobId)
  },

  /**
   * Stop sync (if needed)
   */
  async stopSync(jobId) {
    try {
      await apiClient.post(`/gmail/sync/stop/${jobId}`)
    } catch (error) {
      throw error
    }
  },

  /**
   * Get all applications
   * NO pagination limits - returns ALL fetched emails
   * Response includes gmail_web_url for opening emails
   */
  async getApplications(filters = {}) {
    try {
      const params = new URLSearchParams()
      
      // Add filters if provided
      if (filters.search) params.append('search', filters.search)
      if (filters.status) params.append('status', filters.status)
      if (filters.company) params.append('company', filters.company)
      
      // NO page or limit parameters - backend returns ALL
      const response = await apiClient.get(`/gmail/applications?${params.toString()}`)
      
      return {
        applications: response.data.applications || [],
        total: response.data.total || 0,
        counts: response.data.counts || {},
        warning: response.data.warning, // Backend may warn if data is partial
      }
    } catch (error) {
      if (error.response?.status === 503) {
        // Service unavailable - return empty
        return { applications: [], total: 0, counts: {}, warning: 'Service unavailable' }
      }
      throw error
    }
  },

  /**
   * Get applications grouped by company (summary only)
   * Returns company summaries with counts and status breakdown
   */
  async getApplicationsGroupedByCompany() {
    try {
      const response = await apiClient.get('/gmail/applications/grouped-by-company')
      return response.data
    } catch (error) {
      if (error.response?.status === 503) {
        return { companies: [] }
      }
      throw error
    }
  },

  /**
   * Get dashboard statistics
   * Returns REAL counts from backend, never estimated
   */
  async getStats() {
    try {
      const response = await apiClient.get('/gmail/stats')
      return response.data
    } catch (error) {
      throw error
    }
  },

  /**
   * Production-grade global search
   * Searches across company name, role, subject, and status
   * Returns ranked, paginated results
   */
  async search(query, options = {}) {
    try {
      const params = {
        q: query,
        limit: options.limit || 50,
        offset: options.offset || 0,
      }
      if (options.fuzzy) {
        params.fuzzy = 'true'
      }
      
      const response = await apiClient.get('/gmail/search', { params })
      return response.data
    } catch (error) {
      throw error
    }
  },

  /**
   * Unified advanced search with filters, pagination, and sorting
   * Uses the /applications/search endpoint
   */
  async unifiedSearch(filters = {}) {
    try {
      const params = new URLSearchParams()
      
      if (filters.q) params.append('q', filters.q)
      if (filters.status && Array.isArray(filters.status) && filters.status.length > 0) {
        filters.status.forEach(s => params.append('status', s))
      }
      if (filters.company) params.append('company', filters.company)
      if (filters.role) params.append('role', filters.role)
      if (filters.date_from) params.append('date_from', filters.date_from)
      if (filters.date_to) params.append('date_to', filters.date_to)
      if (filters.page) params.append('page', filters.page)
      if (filters.page_size) params.append('page_size', filters.page_size)
      if (filters.sort_by) params.append('sort_by', filters.sort_by)
      if (filters.sort_order) params.append('sort_order', filters.sort_order)
      
      const response = await apiClient.get(`/gmail/applications/search?${params.toString()}`)
      return response.data
    } catch (error) {
      throw error
    }
  },
}
