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
   * Start Gmail sync
   * Returns { sync_id, status, ... } - sync_id is REQUIRED
   */
  async startSync() {
    try {
      const response = await apiClient.post('/gmail/sync')
      const data = response.data
      
      // VALIDATE: Backend MUST return sync_id
      if (!data.sync_id && !data.job_id) {
        throw new Error('Backend did not return sync_id. Cannot start polling.')
      }
      
      // Normalize: Use sync_id (preferred) or job_id (fallback)
      return {
        ...data,
        sync_id: data.sync_id || data.job_id
      }
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
   * Get sync progress (polling endpoint)
   * Returns real-time counts from backend
   * STRICT: Do not call API if syncId is falsy
   */
  async getSyncProgress(syncId) {
    // STRICT GUARD: Never call API with undefined/null/empty syncId
    if (!syncId || syncId === 'undefined' || syncId === 'null') {
      throw new Error('Cannot get sync progress: syncId is invalid')
    }

    try {
      const response = await apiClient.get(`/gmail/sync/progress/${syncId}`)
      return response.data
    } catch (error) {
      // If service unavailable (503), throw with clear message
      if (error.response?.status === 503) {
        const errorMessage = error.response.data?.detail || 'Gmail service unavailable'
        throw new Error(`Sync service unavailable: ${errorMessage}`)
      }
      throw error
    }
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
}
