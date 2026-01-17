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
   * Returns sync job ID for tracking
   */
  async startSync() {
    try {
      const response = await apiClient.post('/gmail/sync/start')
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
   * Get sync progress (polling endpoint)
   * Returns real-time counts from backend
   */
  async getSyncProgress(jobId) {
    try {
      const response = await apiClient.get(`/gmail/sync/progress/${jobId}`)
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
