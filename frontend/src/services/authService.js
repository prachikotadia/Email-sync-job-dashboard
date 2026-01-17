import apiClient from './apiClient'

export const authService = {
  /**
   * Initiate Google OAuth login
   * Returns the OAuth URL to redirect to
   */
  async initiateLogin() {
    try {
      const response = await apiClient.get('/auth/login')
      return response.data.auth_url
    } catch (error) {
      console.error('Failed to initiate login:', error)
      throw error
    }
  },

  /**
   * Complete OAuth callback and get JWT token
   * @param {string} code - OAuth authorization code
   */
  async handleCallback(code) {
    try {
      const response = await apiClient.post('/auth/callback', { code })
      const { token, user } = response.data
      
      // Store token
      localStorage.setItem('token', token)
      
      return { token, user }
    } catch (error) {
      console.error('Failed to handle callback:', error)
      throw error
    }
  },

  /**
   * Logout - clears frontend state and forces backend to delete cached data
   */
  async logout() {
    try {
      // Call backend to clear all cached email data
      await apiClient.post('/auth/logout')
    } catch (error) {
      console.error('Logout error (continuing anyway):', error)
    } finally {
      // ALWAYS clear frontend state, even if backend call fails
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      
      // Clear any other cached data
      sessionStorage.clear()
    }
  },

  /**
   * Get current user info
   */
  async getCurrentUser() {
    try {
      const response = await apiClient.get('/auth/me')
      return response.data
    } catch (error) {
      console.error('Failed to get current user:', error)
      throw error
    }
  },

  /**
   * Check if user is authenticated (has valid token)
   */
  isAuthenticated() {
    return !!localStorage.getItem('token')
  },
}
