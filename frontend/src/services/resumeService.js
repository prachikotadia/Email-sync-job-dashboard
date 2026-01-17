import apiClient from './apiClient'

/**
 * Resume Service - Production-grade resume management
 * Handles all resume operations: CRUD, upload, export, versioning
 */

export const resumeService = {
  /**
   * Create a new resume
   */
  async createResume(resumeData) {
    try {
      const response = await apiClient.post('/resumes/resumes', resumeData)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to create resume')
      }
      throw new Error(error.message || 'Failed to create resume')
    }
  },

  /**
   * List all resumes for current user
   */
  async listResumes(isActive = null) {
    try {
      const params = {}
      if (isActive !== null) {
        params.is_active = isActive
      }
      const response = await apiClient.get('/resumes/resumes', { params })
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to list resumes')
      }
      throw new Error(error.message || 'Failed to list resumes')
    }
  },

  /**
   * Get a specific resume
   */
  async getResume(resumeId) {
    try {
      const response = await apiClient.get(`/resumes/resumes/${resumeId}`)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to get resume')
      }
      throw new Error(error.message || 'Failed to get resume')
    }
  },

  /**
   * Update a resume
   */
  async updateResume(resumeId, resumeData) {
    try {
      const response = await apiClient.put(`/resumes/resumes/${resumeId}`, resumeData)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to update resume')
      }
      throw new Error(error.message || 'Failed to update resume')
    }
  },

  /**
   * Delete a resume
   */
  async deleteResume(resumeId) {
    try {
      const response = await apiClient.delete(`/resumes/resumes/${resumeId}`)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to delete resume')
      }
      throw new Error(error.message || 'Failed to delete resume')
    }
  },

  /**
   * Upload and parse a resume file
   */
  async uploadResume(file) {
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiClient.post('/resumes/resumes/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // 60 seconds for file upload
      })
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to upload resume')
      }
      throw new Error(error.message || 'Failed to upload resume')
    }
  },

  /**
   * Export resume as PDF
   */
  async exportPDF(resumeId) {
    try {
      const response = await apiClient.post(
        `/resumes/resumes/${resumeId}/export/pdf`,
        {},
        {
          responseType: 'blob',
          timeout: 30000, // 30 seconds for export
        }
      )

      // Download file
      const blob = response.data
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `resume_${resumeId}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)

      return { success: true }
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to export PDF')
      }
      throw new Error(error.message || 'Failed to export PDF')
    }
  },

  /**
   * Export resume as DOCX
   */
  async exportDOCX(resumeId) {
    try {
      const response = await apiClient.post(
        `/resumes/resumes/${resumeId}/export/docx`,
        {},
        {
          responseType: 'blob',
          timeout: 30000, // 30 seconds for export
        }
      )

      // Download file
      const blob = response.data
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `resume_${resumeId}.docx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)

      return { success: true }
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to export DOCX')
      }
      throw new Error(error.message || 'Failed to export DOCX')
    }
  },

  /**
   * Create a version snapshot
   */
  async createVersion(resumeId) {
    try {
      const response = await apiClient.post(`/resumes/resumes/${resumeId}/version`)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to create version')
      }
      throw new Error(error.message || 'Failed to create version')
    }
  },

  /**
   * List all versions of a resume
   */
  async listVersions(resumeId) {
    try {
      const response = await apiClient.get(`/resumes/resumes/${resumeId}/versions`)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to list versions')
      }
      throw new Error(error.message || 'Failed to list versions')
    }
  },
}
