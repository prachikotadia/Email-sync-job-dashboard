/**
 * Profile Service - API calls for profile links
 */
import apiClient from './apiClient'

const profileService = {
  /**
   * Get all profile links for the current user
   */
  async getLinks() {
    try {
      const response = await apiClient.get('/profile/links')
      return response.data
    } catch (error) {
      throw error
    }
  },

  /**
   * Create a new profile link
   * @param {Object} linkData - { type, label?, url }
   */
  async createLink(linkData) {
    try {
      const response = await apiClient.post('/profile/links', linkData)
      return response.data
    } catch (error) {
      throw error
    }
  },

  /**
   * Update an existing profile link
   * @param {string} linkId - Link ID
   * @param {Object} linkData - { type?, label?, url? }
   */
  async updateLink(linkId, linkData) {
    try {
      const response = await apiClient.put(`/profile/links/${linkId}`, linkData)
      return response.data
    } catch (error) {
      throw error
    }
  },

  /**
   * Delete a profile link
   * @param {string} linkId - Link ID
   */
  async deleteLink(linkId) {
    try {
      const response = await apiClient.delete(`/profile/links/${linkId}`)
      return response.data
    } catch (error) {
      throw error
    }
  },
}

export { profileService }
