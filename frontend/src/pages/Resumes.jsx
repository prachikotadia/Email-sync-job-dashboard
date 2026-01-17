import { useState, useRef, useEffect } from 'react'
import { MOCK_MISSING_CONFIRMATIONS } from '../mock/resumes.mock'
import { useResumes } from '../context/ResumesContext'
import { IconUpload, IconCheck, IconEdit, IconDocument, IconAlertCircle, IconX, IconDownload, IconEye } from '../components/icons'
import '../styles/Resumes.css'

export default function Resumes() {
  const [confirmations] = useState(MOCK_MISSING_CONFIRMATIONS)
  const { resumes, uploadResume, removeResume, downloadResume } = useResumes()
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [previewResume, setPreviewResume] = useState(null)
  const fileInputRef = useRef(null)

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric' 
    })
  }

  const handleFileSelect = async (files) => {
    if (!files || files.length === 0) return

    setUploading(true)
    setUploadError(null)

    try {
      // Process files sequentially to avoid quota issues
      for (const file of Array.from(files)) {
        await uploadResume(file)
      }
    } catch (error) {
      setUploadError(error.message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleFileChange = (e) => {
    handleFileSelect(e.target.files)
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

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleRemoveResume = (id) => {
    if (window.confirm('Are you sure you want to remove this resume?')) {
      removeResume(id)
    }
  }

  const handlePreviewResume = (resume) => {
    setPreviewResume(resume)
  }

  const handleClosePreview = () => {
    setPreviewResume(null)
  }

  // Close preview on ESC key
  useEffect(() => {
    if (!previewResume) return
    
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        setPreviewResume(null)
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [previewResume])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (previewResume) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [previewResume])

  return (
    <div className="resumes-page-perfect">
      {/* Header Section */}
      <div className="dashboard-header-section">
        <div className="dashboard-title-area">
          <h1 className="dashboard-main-title">Resumes</h1>
          <p className="dashboard-subtitle">Manage your resume versions and mapping</p>
        </div>
      </div>

      <div className="resumes-content-perfect">
        {/* Main Content */}
        <div className="resumes-main-perfect">
          {/* Upload Card */}
          <div className="content-card-perfect upload-card-perfect">
            <div className="content-card-header">
              <div className="content-card-title-group">
                <div className="content-card-icon">
                  <IconUpload />
                </div>
                <div>
                  <h2 className="content-card-title">Upload Resume</h2>
                  <p className="content-card-subtitle">Add new resume versions</p>
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
                accept=".pdf,application/pdf"
                multiple
                onChange={handleFileChange}
                className="upload-input-hidden"
                id="resume-upload"
                disabled={uploading}
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
                      Drag and drop your PDF here, or click to browse
                    </div>
                    <div className="upload-text-hint">PDF only, max 5MB per file</div>
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
                  <p className="content-card-subtitle">{resumes.length} uploaded</p>
                </div>
              </div>
            </div>
            <div className="resumes-list-perfect">
              {resumes.length === 0 ? (
                <div className="resumes-empty-perfect">
                  <IconDocument />
                  <p>No resumes uploaded yet.</p>
                  <p className="resumes-empty-hint">Upload your first resume to get started</p>
                </div>
              ) : (
                resumes.map((resume) => (
                  <div key={resume.id} className="resume-item-perfect">
                    <div className="resume-item-icon">
                      <IconDocument />
                    </div>
                    <div className="resume-item-content">
                      <div className="resume-item-name">{resume.name}</div>
                      <div className="resume-item-meta">
                        <span className="resume-item-size">{formatFileSize(resume.size)}</span>
                        <span className="resume-item-separator">•</span>
                        <span className="resume-item-date">{formatDate(resume.uploadedAt)}</span>
                      </div>
                    </div>
                    <div className="resume-item-actions">
                      <button
                        type="button"
                        className="resume-action-btn resume-preview-btn"
                        onClick={() => handlePreviewResume(resume)}
                        title="Preview"
                      >
                        <IconEye />
                      </button>
                      <button
                        type="button"
                        className="resume-action-btn resume-download-btn"
                        onClick={() => downloadResume(resume)}
                        title="Download"
                      >
                        <IconDownload />
                      </button>
                      <button
                        type="button"
                        className="resume-action-btn resume-remove-btn"
                        onClick={() => handleRemoveResume(resume.id)}
                        title="Remove"
                      >
                        <IconX />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="resumes-sidebar-perfect">
          <div className="content-card-perfect missing-confirmations-card">
            <div className="content-card-header">
              <div className="content-card-title-group">
                <div className="content-card-icon content-card-icon-warning">
                  <IconAlertCircle />
                </div>
                <div>
                  <h2 className="content-card-title">Missing Confirmations</h2>
                  <p className="content-card-subtitle">{confirmations.length} items need attention</p>
                </div>
              </div>
            </div>
            <p className="missing-desc-perfect">
              We found {confirmations.length} applications where the resume used is unclear or low confidence.
            </p>
            <div className="missing-list-perfect">
              {confirmations.map((item) => (
                <div key={item.id} className="missing-item-perfect">
                  <div className="missing-item-header">
                    <div className="missing-company">{item.company}</div>
                    <div className="missing-role">{item.role}</div>
                    <div className="missing-time">{item.timeAgo}</div>
                  </div>
                  <div className="missing-suggestion">
                    <span className="missing-suggestion-label">AI Suggestion:</span>
                    <span className="missing-suggestion-file">{item.suggestedResume}</span>
                    <span className={`missing-confidence confidence-${item.confidence >= 90 ? 'high' : 'medium'}`}>
                      {item.confidence}%
                    </span>
                  </div>
                  <div className="missing-actions">
                    <button type="button" className="missing-confirm-btn">
                      <IconCheck />
                      <span>Confirm</span>
                    </button>
                    <button type="button" className="missing-edit-btn" aria-label="Edit">
                      <IconEdit />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Resume Preview Modal */}
      {previewResume && (
        <div className="resume-preview-modal" onClick={handleClosePreview}>
          <div className="resume-preview-content" onClick={(e) => e.stopPropagation()}>
            <div className="resume-preview-header">
              <div className="resume-preview-title">
                <IconDocument />
                <span>{previewResume.name}</span>
              </div>
              <button
                type="button"
                className="resume-preview-close"
                onClick={handleClosePreview}
                aria-label="Close preview"
              >
                <IconX />
              </button>
            </div>
            <div className="resume-preview-body">
              <iframe
                src={previewResume.data}
                title={previewResume.name}
                className="resume-preview-iframe"
              />
            </div>
            <div className="resume-preview-footer">
              <button
                type="button"
                className="resume-preview-download-btn"
                onClick={() => {
                  downloadResume(previewResume)
                  handleClosePreview()
                }}
              >
                <IconDownload />
                <span>Download</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
