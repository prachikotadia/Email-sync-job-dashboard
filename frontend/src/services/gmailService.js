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
   * Start Gmail sync (new job-based system)
   * Returns { jobId, status, startedAt }
   */
  async startSync() {
    try {
      const response = await apiClient.post('/gmail/sync/start')
      const data = response.data
      
      // VALIDATE: Backend MUST return jobId
      if (!data.jobId) {
        throw new Error('Backend did not return jobId. Cannot start polling.')
      }
      
      return data
    } catch (error) {
      if (error.response?.status === 409) {
        // Sync already running - try to get existing job
        const status = await this.getSyncStatus()
        if (status.jobId) {
          return { jobId: status.jobId, status: status.status }
        }
        const message = error.response.data?.detail || 'Sync is already running'
        throw new Error(message)
      }
      throw error
    }
  },

  /**
   * Get current sync status for user
   * Returns { jobId, status, ... } or { jobId: null, status: null }
   */
  async getSyncStatus() {
    try {
      const response = await apiClient.get('/gmail/sync/status')
      return response.data
    } catch (error) {
      // If service unavailable, return null status
      if (error.response?.status === 503) {
        return { jobId: null, status: null }
      }
      throw error
    }
  },

  /**
   * Get sync progress (polling endpoint) - job-based system
   * Returns real-time counts from backend
   * STRICT: Do not call API if jobId is falsy
   */
  async getSyncProgress(jobId) {
    // STRICT GUARD: Never call API with undefined/null/empty jobId
    if (!jobId || jobId === 'undefined' || jobId === 'null') {
      throw new Error('Cannot get sync progress: jobId is invalid')
    }

    try {
      const response = await apiClient.get(`/gmail/sync/progress/${jobId}`)
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
   * Get sync logs for a job
   * Returns logs after a specific sequence number
   */
  async getSyncLogs(jobId, afterSeq = 0) {
    // STRICT GUARD: Never call API with undefined/null/empty jobId
    if (!jobId || jobId === 'undefined' || jobId === 'null') {
      throw new Error('Cannot get sync logs: jobId is invalid')
    }

    try {
      const response = await apiClient.get(`/gmail/sync/logs/${jobId}`, {
        params: { after_seq: afterSeq }
      })
      return response.data
    } catch (error) {
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
