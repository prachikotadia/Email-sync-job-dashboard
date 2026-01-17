import apiClient from './apiClient'

/**
 * Export Service - Production-grade export functionality
 * Handles all export formats: CSV, Excel, JSON, PDF
 */

export const exportService = {
  /**
   * Export applications in specified format
   * @param {Object} options - Export configuration
   * @param {string} options.format - Format: 'csv', 'xlsx', 'json', 'pdf'
   * @param {string} options.category - Category filter: 'ALL', 'APPLIED', 'REJECTED', 'INTERVIEW', 'OFFER', 'GHOSTED'
   * @param {Object} options.dateRange - Date range: { from: 'YYYY-MM-DD' | null, to: 'YYYY-MM-DD' | null }
   * @param {Array<string>} options.fields - Fields to include
   * @returns {Promise<Blob>} File blob for download
   */
  async exportApplications({ format, category, dateRange, fields }) {
    try {
      const response = await apiClient.post(
        '/exports/export',
        {
          format,
          category,
          dateRange,
          fields,
        },
        {
          responseType: 'blob', // Important for file downloads
          timeout: 120000, // 2 minutes for large exports
        }
      )

      return response.data
    } catch (error) {
      if (error.response) {
        // Try to parse error message from blob if possible
        if (error.response.data instanceof Blob) {
          const text = await error.response.data.text()
          try {
            const errorData = JSON.parse(text)
            throw new Error(errorData.detail || 'Export failed')
          } catch {
            throw new Error('Export failed')
          }
        }
        const message = error.response.data?.detail || error.response.data?.message || 'Export failed'
        throw new Error(message)
      } else if (error.request) {
        throw new Error('Network error: Could not reach server')
      } else {
        throw new Error(error.message || 'Export failed')
      }
    }
  },

  /**
   * Download file blob
   * @param {Blob} blob - File blob
   * @param {string} filename - Filename for download
   */
  downloadFile(blob, filename) {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  },
}
