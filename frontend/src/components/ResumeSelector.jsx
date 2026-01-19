import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { resumeService } from '../services/resumeService'
import { IconChevronDown, IconPlus, IconUpload, IconCheck, IconX, IconFile, IconFileText } from './icons'
import { toast } from '../utils/toast'

/**
 * Resume Selector Component
 * Reusable dropdown for selecting resumes in application forms/details
 * 
 * Features:
 * - Shows default resume preselected
 * - Option to upload new resume inline
 * - Shows resume name + badge
 * - Updates backend immediately on change
 */
export default function ResumeSelector({ 
  applicationId, 
  currentResumeId = null, 
  onResumeChange = () => {},
  disabled = false,
  resumes: externalResumes = null, // Optional: if provided, use these instead of loading
  onResumesChange = null // Optional: callback to update parent's resumes list
}) {
  const [resumes, setResumes] = useState(externalResumes || [])
  const [loading, setLoading] = useState(!externalResumes) // Only loading if resumes not provided
  const [isOpen, setIsOpen] = useState(false)
  const [selectedResumeId, setSelectedResumeId] = useState(currentResumeId)
  const [uploading, setUploading] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const dropdownRef = useRef(null)
  const dropdownPortalRef = useRef(null)
  const fileInputRef = useRef(null)
  const loadingRef = useRef(false) // Guard against concurrent loads

  // Update local resumes when external resumes change
  useEffect(() => {
    if (externalResumes) {
      setResumes(externalResumes)
      setLoading(false)
    }
  }, [externalResumes])

  // Load resumes on mount (only if not provided externally)
  useEffect(() => {
    if (!externalResumes && !loadingRef.current) {
      loadResumes()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run once on mount

  // Update selected resume when currentResumeId changes
  useEffect(() => {
    setSelectedResumeId(currentResumeId)
  }, [currentResumeId])

  // Update dropdown position on scroll/resize when open
  useEffect(() => {
    if (!isOpen || !dropdownRef.current) return

    const updatePosition = () => {
      if (dropdownPortalRef.current && dropdownRef.current) {
        const rect = dropdownRef.current.getBoundingClientRect()
        const viewportHeight = window.innerHeight
        const viewportWidth = window.innerWidth
        const dropdownHeight = 300 // max height
        
        let top = rect.bottom + 4
        let left = rect.left
        let width = rect.width
        
        // If dropdown would go below viewport, show it above instead
        if (top + dropdownHeight > viewportHeight && rect.top > dropdownHeight) {
          top = rect.top - dropdownHeight - 4
        }
        
        // Ensure dropdown doesn't go off right edge
        if (left + width > viewportWidth) {
          left = viewportWidth - width - 10
        }
        
        // Ensure dropdown doesn't go off left edge
        if (left < 10) {
          left = 10
          width = Math.min(width, viewportWidth - 20)
        }
        
        dropdownPortalRef.current.style.top = `${Math.max(10, top)}px`
        dropdownPortalRef.current.style.left = `${left}px`
        dropdownPortalRef.current.style.width = `${width}px`
      }
    }

    updatePosition()
    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)

    return () => {
      window.removeEventListener('scroll', updatePosition, true)
      window.removeEventListener('resize', updatePosition)
    }
  }, [isOpen])

  // Close dropdown when clicking outside (works with portal)
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        dropdownRef.current && 
        !dropdownRef.current.contains(event.target) &&
        dropdownPortalRef.current &&
        !dropdownPortalRef.current.contains(event.target)
      ) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      // Use a small delay to avoid immediate closure
      const timeoutId = setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside)
      }, 10)
      return () => {
        clearTimeout(timeoutId)
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [isOpen])

  const loadResumes = async () => {
    // Guard against concurrent calls
    if (loadingRef.current) {
      return
    }
    
    loadingRef.current = true
    
    try {
      setLoading(true)
      const data = await resumeService.listResumes()
      setResumes(data)
      
      // If no resume selected and there's a default, select it
      if (!selectedResumeId && data.length > 0) {
        const defaultResume = data.find(r => r.is_default)
        if (defaultResume) {
          setSelectedResumeId(defaultResume.id)
          if (applicationId) {
            await handleResumeSelect(defaultResume.id)
          }
        }
      }
    } catch (err) {
      toast.error(err.message || 'Failed to load resumes')
    } finally {
      setLoading(false)
      loadingRef.current = false
    }
  }

  const handleResumeSelect = async (resumeId) => {
    if (!applicationId) {
      // Just update selection if no application ID (for forms)
      setSelectedResumeId(resumeId)
      onResumeChange(resumeId)
      setIsOpen(false)
      return
    }

    try {
      await resumeService.linkResumeToApplication(applicationId, resumeId)
      setSelectedResumeId(resumeId)
      onResumeChange(resumeId)
      setIsOpen(false)
      toast.success('Resume linked successfully')
    } catch (err) {
      toast.error(err.message || 'Failed to link resume')
    }
  }

  const handleFileUpload = async (file) => {
    if (!file) return

    setUploading(true)
    try {
      // Validate file
      if (!file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
        throw new Error('Only PDF and DOCX files are supported')
      }

      if (file.size > 5 * 1024 * 1024) {
        throw new Error('File size exceeds 5MB limit')
      }

      // Upload
      const newResume = await resumeService.uploadResume(file)
      
      // Reload resumes (or update parent's list if provided)
      if (externalResumes && onResumesChange) {
        // Update parent's resumes list
        const updatedResumes = await resumeService.listResumes()
        onResumesChange(updatedResumes)
        setResumes(updatedResumes)
      } else {
        // Load locally
        await loadResumes()
      }
      
      // Select the new resume
      await handleResumeSelect(newResume.id)
      
      toast.success('Resume uploaded and linked')
      setShowUploadModal(false)
    } catch (err) {
      toast.error(err.message || 'Failed to upload resume')
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const selectedResume = resumes.find(r => r.id === selectedResumeId)
  const defaultResume = resumes.find(r => r.is_default)

  return (
    <div className="resume-selector" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled || loading}
        className="resume-selector-button"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.5rem 0.75rem',
          background: disabled ? 'rgba(255, 255, 255, 0.02)' : 'rgba(255, 255, 255, 0.03)',
          border: '1px solid #334155',
          borderRadius: '0.5rem',
          color: disabled ? '#475569' : '#e2e8f0',
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontSize: '0.875rem',
          width: '100%',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: 0 }}>
          {loading ? (
            <span>Loading...</span>
          ) : selectedResume ? (
            <>
              {selectedResume.file_type === 'pdf' ? <IconFile /> : <IconFileText />}
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {selectedResume.file_name}
              </span>
              {selectedResume.is_default && (
                <span style={{ fontSize: '0.75rem', color: '#fbbf24' }} title="Default Resume">⭐</span>
              )}
            </>
          ) : (
            <span style={{ color: '#94a3b8' }}>Select resume...</span>
          )}
        </div>
        <IconChevronDown style={{ 
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s',
        }} />
      </button>

      {isOpen && !disabled && createPortal(
        <div 
          ref={dropdownPortalRef}
          className="resume-selector-dropdown" 
          style={{
            position: 'fixed',
            top: dropdownRef.current ? `${dropdownRef.current.getBoundingClientRect().bottom + 4}px` : '0',
            left: dropdownRef.current ? `${dropdownRef.current.getBoundingClientRect().left}px` : '0',
            width: dropdownRef.current ? `${dropdownRef.current.getBoundingClientRect().width}px` : '200px',
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '0.5rem',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
            zIndex: 9999,
            maxHeight: '300px',
            overflowY: 'auto',
          }}
        >
          {loading ? (
            <div style={{ padding: '1rem', textAlign: 'center', color: '#94a3b8' }}>
              Loading resumes...
            </div>
          ) : resumes.length === 0 ? (
            <div style={{ padding: '1rem', textAlign: 'center', color: '#94a3b8' }}>
              <div style={{ marginBottom: '0.5rem' }}>No resumes uploaded</div>
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false)
                  setShowUploadModal(true)
                }}
                style={{
                  padding: '0.5rem 1rem',
                  background: '#3b82f6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                Upload Resume
              </button>
            </div>
          ) : (
            <>
              {resumes.map((resume) => (
                <button
                  key={resume.id}
                  type="button"
                  onClick={() => handleResumeSelect(resume.id)}
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    background: selectedResumeId === resume.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                    border: 'none',
                    color: '#e2e8f0',
                    cursor: 'pointer',
                    fontSize: '0.875rem',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    transition: 'background 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    if (selectedResumeId !== resume.id) {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (selectedResumeId !== resume.id) {
                      e.currentTarget.style.background = 'transparent'
                    }
                  }}
                >
                  {resume.file_type === 'pdf' ? <IconFile /> : <IconFileText />}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {resume.file_name}
                      </span>
                      {resume.is_default && (
                        <span style={{ fontSize: '0.75rem', color: '#fbbf24' }} title="Default Resume">⭐</span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                      {resume.file_type.toUpperCase()} • {(resume.file_size_kb / 1024).toFixed(2)} MB
                    </div>
                  </div>
                  {selectedResumeId === resume.id && (
                    <IconCheck style={{ color: '#3b82f6', flexShrink: 0 }} />
                  )}
                </button>
              ))}
              <div style={{ borderTop: '1px solid #334155', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => {
                    setIsOpen(false)
                    setShowUploadModal(true)
                  }}
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    background: 'transparent',
                    border: 'none',
                    color: '#60a5fa',
                    cursor: 'pointer',
                    fontSize: '0.875rem',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent'
                  }}
                >
                  <IconPlus />
                  <span>Upload New Resume</span>
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && createPortal(
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2000,
            padding: '1rem',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !uploading) {
              setShowUploadModal(false)
            }
          }}
        >
          <div
            style={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '1rem',
              padding: '2rem',
              maxWidth: '500px',
              width: '100%',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: 0, color: '#e2e8f0', fontSize: '1.5rem', fontWeight: '600' }}>
                Upload Resume
              </h2>
              <button
                type="button"
                onClick={() => !uploading && setShowUploadModal(false)}
                disabled={uploading}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: uploading ? 'not-allowed' : 'pointer',
                  padding: '0.5rem',
                  display: 'flex',
                  alignItems: 'center',
                  opacity: uploading ? 0.5 : 1,
                }}
              >
                <IconX />
              </button>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) {
                    handleFileUpload(file)
                  }
                }}
                disabled={uploading}
                style={{ display: 'none' }}
              />
              <label
                htmlFor="resume-upload-inline"
                style={{
                  display: 'block',
                  padding: '2rem',
                  border: '2px dashed #334155',
                  borderRadius: '0.5rem',
                  textAlign: 'center',
                  cursor: uploading ? 'not-allowed' : 'pointer',
                  opacity: uploading ? 0.5 : 1,
                }}
                onClick={() => {
                  if (!uploading) {
                    fileInputRef.current?.click()
                  }
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  id="resume-upload-inline"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) {
                      handleFileUpload(file)
                    }
                  }}
                  disabled={uploading}
                  style={{ display: 'none' }}
                />
                {uploading ? (
                  <>
                    <div style={{ marginBottom: '1rem' }}>
                      <div className="upload-spinner" style={{ 
                        width: '48px', 
                        height: '48px', 
                        border: '3px solid #334155',
                        borderTopColor: '#3b82f6',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite',
                        margin: '0 auto',
                      }} />
                    </div>
                    <div style={{ color: '#e2e8f0', fontWeight: '500' }}>Uploading...</div>
                  </>
                ) : (
                  <>
                    <IconUpload style={{ marginBottom: '1rem', color: '#60a5fa' }} />
                    <div style={{ color: '#e2e8f0', fontWeight: '500', marginBottom: '0.5rem' }}>
                      Click to upload or drag and drop
                    </div>
                    <div style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                      PDF or DOCX, max 5MB
                    </div>
                  </>
                )}
              </label>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
