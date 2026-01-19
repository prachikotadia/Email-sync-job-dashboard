import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useAuth } from '../context/AuthContext'
import { resumeService } from '../services/resumeService'
import { IconUpload, IconDocument, IconX, IconDownload, IconEdit, IconPlus, IconCheck, IconAlertCircle, IconFile, IconFileText, IconTrash, IconStar, IconEye } from '../components/icons'
import { toast } from '../utils/toast'
import '../styles/Resumes.css'

export default function Resumes() {
  const { user, isGuest } = useAuth()
  const [resumes, setResumes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [editingResume, setEditingResume] = useState(null)
  const [editingName, setEditingName] = useState('')
  const [showRenameModal, setShowRenameModal] = useState(false)
  const [deletingResume, setDeletingResume] = useState(null)
  const [previewingResume, setPreviewingResume] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const fileInputRef = useRef(null)

  // Load resumes on mount
  useEffect(() => {
    if (!isGuest) {
      loadResumes()
    } else {
      setLoading(false)
    }
  }, [isGuest])

  // Cleanup preview URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) {
        window.URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const loadResumes = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await resumeService.listResumes()
      setResumes(data)
    } catch (err) {
      setError(err.message || 'Failed to load resumes')
      toast.error(err.message || 'Failed to load resumes')
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = async (files) => {
    if (!files || files.length === 0) return
    if (isGuest) {
      setUploadError('Upload is disabled in Guest Mode')
      return
    }

    setUploading(true)
    setUploadError(null)

    try {
      const file = files[0]
      
      // Validate file type
      if (!file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
        throw new Error('Only PDF and DOCX files are supported')
      }

      // Validate file size (5MB max)
      if (file.size > 5 * 1024 * 1024) {
        throw new Error('File size exceeds 5MB limit')
      }

      // Upload file
      await resumeService.uploadResume(file)
      
      // Reload resumes
      await loadResumes()
      toast.success('Resume uploaded successfully')
    } catch (err) {
      const errorMsg = err.message || 'Failed to upload resume'
      setUploadError(errorMsg)
      toast.error(errorMsg)
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    handleFileSelect(e.dataTransfer.files)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
  }

  const handleDeleteResume = async (resumeId) => {
    if (!window.confirm('Are you sure you want to delete this resume? This action cannot be undone.')) {
      return
    }

    setDeletingResume(resumeId)
    try {
      await resumeService.deleteResume(resumeId)
      await loadResumes()
      toast.success('Resume deleted successfully')
    } catch (err) {
      const errorMsg = err.message || 'Failed to delete resume'
      toast.error(errorMsg)
      setError(errorMsg)
    } finally {
      setDeletingResume(null)
    }
  }

  const handleSetDefault = async (resumeId) => {
    try {
      await resumeService.setDefaultResume(resumeId)
      await loadResumes()
      toast.success('Default resume updated')
    } catch (err) {
      const errorMsg = err.message || 'Failed to set default resume'
      toast.error(errorMsg)
      setError(errorMsg)
    }
  }

  const handleRename = async (resumeId, newName) => {
    if (!newName || !newName.trim()) {
      toast.error('Resume name cannot be empty')
      return
    }

    try {
      await resumeService.renameResume(resumeId, newName.trim())
      await loadResumes()
      toast.success('Resume renamed successfully')
      setShowRenameModal(false)
      setEditingResume(null)
      setEditingName('')
    } catch (err) {
      const errorMsg = err.message || 'Failed to rename resume'
      toast.error(errorMsg)
    }
  }

  const handleDownload = async (resumeId) => {
    try {
      await resumeService.downloadResume(resumeId)
      toast.success('Resume download started')
    } catch (err) {
      const errorMsg = err.message || 'Failed to download resume'
      toast.error(errorMsg)
    }
  }

  const handlePreview = async (resumeId) => {
    try {
      const resume = resumes.find(r => r.id === resumeId)
      if (!resume) {
        toast.error('Resume not found in your list. Please refresh the page.')
        return
      }

      setPreviewingResume(resume)
      const result = await resumeService.previewResume(resumeId)
      setPreviewUrl(result.blobUrl)
    } catch (err) {
      let errorMsg = 'Failed to preview resume'
      if (err.response?.status === 404) {
        errorMsg = 'Resume not found. It may have been deleted. Please refresh the page.'
        // Reload resumes to sync state
        await loadResumes()
      } else if (err.response?.status === 403) {
        errorMsg = 'You do not have permission to view this resume.'
      } else if (err.message) {
        errorMsg = err.message
      }
      toast.error(errorMsg)
      setPreviewingResume(null)
      setPreviewUrl(null)
    }
  }

  const closePreview = () => {
    if (previewUrl) {
      window.URL.revokeObjectURL(previewUrl)
    }
    setPreviewingResume(null)
    setPreviewUrl(null)
  }

  const openRenameModal = (resume) => {
    setEditingResume(resume)
    setEditingName(resume.file_name)
    setShowRenameModal(true)
  }

  const formatFileSize = (kb) => {
    if (kb < 1024) return `${kb} KB`
    return `${(kb / 1024).toFixed(2)} MB`
  }

  const formatDate = (dateString) => {
    if (!dateString) return '—'
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
    } catch {
      return dateString
    }
  }

  return (
    <div className="resumes-page-perfect">
      {/* Header Section */}
      <div className="dashboard-header-section">
        <div className="dashboard-title-area">
          <h1 className="dashboard-main-title">Resume Library</h1>
          <p className="dashboard-subtitle">Manage your resumes and link them to applications</p>
        </div>
      </div>

      {error && (
        <div className="resume-error-banner-perfect">
          <div className="resume-error-content">
            <IconAlertCircle />
            <span>{error}</span>
          </div>
          <button 
            onClick={() => setError(null)}
            className="resume-error-close-btn-perfect"
            aria-label="Close error"
          >
            <IconX />
          </button>
        </div>
      )}

      <div className="resumes-content-perfect">
        {/* Upload Card */}
        <div className="content-card-perfect upload-card-perfect">
          <div className="content-card-header">
            <div className="content-card-title-group">
              <div className="content-card-icon">
                <IconUpload />
              </div>
              <div>
                <h2 className="content-card-title">Upload Resume</h2>
                <p className="content-card-subtitle">Upload PDF or DOCX files (max 5MB)</p>
              </div>
            </div>
          </div>
          <div
            className={`upload-area-perfect ${dragActive ? 'drag-active' : ''} ${uploading ? 'uploading' : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => handleFileSelect(e.target.files)}
              className="upload-input-hidden"
              id="resume-upload"
              disabled={uploading || isGuest}
            />
            <label htmlFor="resume-upload" className="upload-label-perfect">
              {uploading ? (
                <>
                  <div className="upload-icon-wrapper uploading">
                    <div className="upload-spinner" />
                  </div>
                  <div className="upload-text-primary">Uploading...</div>
                  <div className="upload-text-secondary">Please wait</div>
                </>
              ) : (
                <>
                  <div className="upload-icon-wrapper">
                    <IconUpload />
                  </div>
                  <div className="upload-text-primary">Upload new resume</div>
                  <div className="upload-text-secondary">
                    Drag and drop your PDF or DOCX here, or click to browse
                  </div>
                  <div className="upload-text-hint">PDF or DOCX only, max 5MB</div>
                </>
              )}
            </label>
            {uploadError && (
              <div className="upload-error-message">{uploadError}</div>
            )}
          </div>
        </div>

        {/* Resumes List Card */}
        <div className="content-card-perfect resumes-list-card-perfect">
          <div className="content-card-header">
            <div className="content-card-title-group">
              <div className="content-card-icon">
                <IconDocument />
              </div>
              <div>
                <h2 className="content-card-title">Your Resumes</h2>
                <p className="content-card-subtitle">{resumes.length} resume{resumes.length !== 1 ? 's' : ''} uploaded</p>
              </div>
            </div>
          </div>

          <div className="resumes-list-content">
            {loading ? (
              <div className="resumes-loading-perfect">
                <div className="resumes-loading-spinner-wrapper">
                  <div className="resumes-loading-spinner" />
                </div>
                <span className="resumes-loading-text">Loading resumes...</span>
              </div>
            ) : resumes.length === 0 ? (
              <div className="resumes-empty-state-perfect">
                <div className="resumes-empty-icon-wrapper">
                  <IconDocument />
                </div>
                <h3 className="resumes-empty-title">No resumes uploaded</h3>
                <p className="resumes-empty-description">Upload your first resume to get started with job applications</p>
              </div>
            ) : (
              <div className="resumes-grid-perfect">
                {resumes.map((resume) => (
                  <div key={resume.id} className="resume-card-perfect">
                    <div className="resume-card-header-perfect">
                      <div className="resume-card-icon-perfect">
                        {resume.file_type === 'pdf' ? <IconFile /> : <IconFileText />}
                      </div>
                      <div className="resume-card-info-perfect">
                        <div className="resume-card-name-row">
                          <h3 className="resume-card-name-perfect">{resume.file_name}</h3>
                          {resume.is_default && (
                            <span className="resume-default-badge-perfect" title="Default Resume">
                              <IconStar />
                              <span>Default</span>
                            </span>
                          )}
                        </div>
                        <div className="resume-card-meta-perfect">
                          <span className="resume-file-type-badge">{resume.file_type.toUpperCase()}</span>
                          <span className="resume-file-size-text">{formatFileSize(resume.file_size_kb)}</span>
                          {resume.usage_count > 0 && (
                            <span className="resume-usage-badge">{resume.usage_count} application{resume.usage_count !== 1 ? 's' : ''}</span>
                          )}
                        </div>
                        <div className="resume-card-date-perfect">
                          <span>Uploaded {formatDate(resume.created_at)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="resume-card-actions-perfect">
                      <button
                        type="button"
                        onClick={() => handlePreview(resume.id)}
                        className="resume-action-btn-perfect resume-action-btn-primary"
                        title="Preview resume"
                      >
                        <IconEye />
                        <span>Preview</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDownload(resume.id)}
                        className="resume-action-btn-perfect resume-action-btn-secondary"
                        title="Download resume"
                      >
                        <IconDownload />
                        <span>Download</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => openRenameModal(resume)}
                        className="resume-action-btn-perfect resume-action-btn-tertiary"
                        title="Rename resume"
                      >
                        <IconEdit />
                        <span>Rename</span>
                      </button>
                      {!resume.is_default && (
                        <button
                          type="button"
                          onClick={() => handleSetDefault(resume.id)}
                          className="resume-action-btn-perfect resume-action-btn-star"
                          title="Set as default"
                        >
                          <IconStar />
                          <span>Set Default</span>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDeleteResume(resume.id)}
                        disabled={deletingResume === resume.id}
                        className="resume-action-btn-perfect resume-action-btn-danger"
                        title="Delete resume"
                      >
                        <IconTrash />
                        <span>{deletingResume === resume.id ? 'Deleting...' : 'Delete'}</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Preview Modal - Perfect */}
      {previewingResume && previewUrl && createPortal(
        <div
          className="resume-preview-modal-perfect"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              closePreview()
            }
          }}
        >
          <div className="resume-preview-modal-content-perfect">
            <div className="resume-preview-modal-header-perfect">
              <div className="resume-preview-modal-title-group">
                {previewingResume.file_type === 'pdf' ? <IconFile /> : <IconFileText />}
                <h2 className="resume-preview-modal-title">{previewingResume.file_name}</h2>
              </div>
              <div className="resume-preview-modal-actions">
                <button
                  type="button"
                  onClick={() => handleDownload(previewingResume.id)}
                  className="resume-preview-download-btn-perfect"
                  title="Download resume"
                >
                  <IconDownload />
                  <span>Download</span>
                </button>
                <button
                  type="button"
                  onClick={closePreview}
                  className="resume-preview-close-btn-perfect"
                  aria-label="Close preview"
                >
                  <IconX />
                </button>
              </div>
            </div>
            <div className="resume-preview-modal-body-perfect">
              {previewingResume.file_type === 'pdf' ? (
                <iframe
                  src={previewUrl}
                  className="resume-preview-iframe-perfect"
                  title={`Preview of ${previewingResume.file_name}`}
                />
              ) : (
                <div className="resume-preview-docx-notice">
                  <IconFileText />
                  <h3>DOCX Preview</h3>
                  <p>DOCX files cannot be previewed in the browser. Please download the file to view it.</p>
                  <button
                    type="button"
                    onClick={() => handleDownload(previewingResume.id)}
                    className="resume-preview-download-btn-perfect"
                  >
                    <IconDownload />
                    <span>Download to View</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Rename Modal - Perfect */}
      {showRenameModal && editingResume && createPortal(
        <div
          className="resume-rename-modal-perfect"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowRenameModal(false)
              setEditingResume(null)
              setEditingName('')
            }
          }}
        >
          <div className="resume-rename-modal-content">
            <div className="resume-rename-modal-header">
              <h2 className="resume-rename-modal-title">Rename Resume</h2>
              <button
                type="button"
                onClick={() => {
                  setShowRenameModal(false)
                  setEditingResume(null)
                  setEditingName('')
                }}
                className="resume-rename-modal-close"
                aria-label="Close modal"
              >
                <IconX />
              </button>
            </div>

            <div className="resume-rename-modal-body">
              <label className="resume-rename-label">Resume Name</label>
              <input
                type="text"
                value={editingName}
                onChange={(e) => setEditingName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleRename(editingResume.id, editingName)
                  } else if (e.key === 'Escape') {
                    setShowRenameModal(false)
                    setEditingResume(null)
                    setEditingName('')
                  }
                }}
                placeholder="Enter resume name"
                className="resume-rename-input"
                autoFocus
              />
            </div>

            <div className="resume-rename-modal-footer">
              <button
                type="button"
                onClick={() => {
                  setShowRenameModal(false)
                  setEditingResume(null)
                  setEditingName('')
                }}
                className="resume-rename-btn-cancel"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleRename(editingResume.id, editingName)}
                disabled={!editingName || !editingName.trim()}
                className="resume-rename-btn-save"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

