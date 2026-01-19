import apiClient from './apiClient'

/**
 * Resume Service - File-based resume management
 * Handles resume file upload, management, and linking to applications
 */

export const resumeService = {
  /**
   * Upload a resume file (PDF or DOCX)
   */
  async uploadResume(file, fileName = null) {
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const params = {}
      if (fileName) {
        params.file_name = fileName
      }

      const response = await apiClient.post('/resumes/upload', formData, {
        params,
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
   * List all resumes for current user
   */
  async listResumes() {
    try {
      const response = await apiClient.get('/resumes')
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
      const response = await apiClient.get(`/resumes/${resumeId}`)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to get resume')
      }
      throw new Error(error.message || 'Failed to get resume')
    }
  },

  /**
   * Rename a resume
   */
  async renameResume(resumeId, fileName) {
    try {
      const response = await apiClient.put(`/resumes/${resumeId}/rename`, {
        file_name: fileName,
      })
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to rename resume')
      }
      throw new Error(error.message || 'Failed to rename resume')
    }
  },

  /**
   * Set a resume as default
   */
  async setDefaultResume(resumeId) {
    try {
      const response = await apiClient.post(`/resumes/${resumeId}/set-default`)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to set default resume')
      }
      throw new Error(error.message || 'Failed to set default resume')
    }
  },

  /**
   * Delete a resume
   */
  async deleteResume(resumeId) {
    try {
      await apiClient.delete(`/resumes/${resumeId}`)
      return true
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to delete resume')
      }
      throw new Error(error.message || 'Failed to delete resume')
    }
  },

  /**
   * Download resume file
   */
  async downloadResume(resumeId) {
    try {
      const response = await apiClient.get(`/resumes/${resumeId}/download`, {
        responseType: 'blob',
        timeout: 60000,
      })

      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers['content-disposition']
      let filename = `resume_${resumeId}.pdf`
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }

      // Create download link
      const blob = response.data
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)

      return { success: true }
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to download resume')
      }
      throw new Error(error.message || 'Failed to download resume')
    }
  },

  /**
   * Preview resume file (returns blob URL for preview)
   */
  async previewResume(resumeId) {
    try {
      const response = await apiClient.get(`/resumes/${resumeId}/preview`, {
        responseType: 'blob',
        timeout: 60000,
      })

      // Create blob URL for preview
      const blob = response.data
      const blobUrl = window.URL.createObjectURL(blob)
      
      return { 
        success: true, 
        blobUrl,
        blob,
        contentType: response.headers['content-type'] || 'application/pdf'
      }
    } catch (error) {
      // Handle blob error responses (they come as JSON in the blob)
      if (error.response && error.response.data instanceof Blob) {
        try {
          const text = await error.response.data.text()
          const errorData = JSON.parse(text)
          throw new Error(errorData.detail || 'Failed to preview resume')
        } catch {
          // If parsing fails, use status code
          if (error.response.status === 404) {
            throw new Error('Resume not found. It may have been deleted.')
          } else if (error.response.status === 403) {
            throw new Error('You do not have permission to view this resume.')
          }
          throw new Error('Failed to preview resume')
        }
      }
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to preview resume')
      }
      throw new Error(error.message || 'Failed to preview resume')
    }
  },

  /**
   * Get default resume
   */
  async getDefaultResume() {
    try {
      const response = await apiClient.get('/resumes/default')
      return response.data
    } catch (error) {
      if (error.response) {
        // 404 is okay - no default resume set
        if (error.response.status === 404) {
          return { resume: null }
        }
        throw new Error(error.response.data?.detail || 'Failed to get default resume')
      }
      throw new Error(error.message || 'Failed to get default resume')
    }
  },

  /**
   * Link resume to application
   */
  async linkResumeToApplication(applicationId, resumeId) {
    try {
      const response = await apiClient.post(`/resumes/applications/${applicationId}/resume/${resumeId}`)
      return response.data
    } catch (error) {
      if (error.response) {
        throw new Error(error.response.data?.detail || 'Failed to link resume')
      }
      throw new Error(error.message || 'Failed to link resume')
    }
  },

  /**
   * Get resume for application
   */
  async getApplicationResume(applicationId) {
    try {
      const response = await apiClient.get(`/resumes/applications/${applicationId}/resume`)
      return response.data
    } catch (error) {
      if (error.response) {
        // 404 is okay - no resume linked
        if (error.response.status === 404) {
          return { resume: null }
        }
        throw new Error(error.response.data?.detail || 'Failed to get application resume')
      }
      throw new Error(error.message || 'Failed to get application resume')
    }
  },
}
