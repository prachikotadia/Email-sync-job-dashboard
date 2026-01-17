import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { resumeService } from '../services/resumeService'
import { IconUpload, IconDocument, IconX, IconDownload, IconEdit, IconPlus, IconCheck, IconAlertCircle, IconFile, IconFileText } from '../components/icons'
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
  const [showCreateModal, setShowCreateModal] = useState(false)
  const fileInputRef = useRef(null)

  // Load resumes on mount
  useEffect(() => {
    if (!isGuest) {
      loadResumes()
    } else {
      setLoading(false)
    }
  }, [isGuest])

  const loadResumes = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await resumeService.listResumes()
      setResumes(data)
    } catch (err) {
      setError(err.message || 'Failed to load resumes')
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
      const file = files[0] // Handle one file at a time
      
      // Validate file type
      if (!file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
        throw new Error('Only PDF and DOCX files are supported')
      }

      // Validate file size (10MB max)
      if (file.size > 10 * 1024 * 1024) {
        throw new Error('File size exceeds 10MB limit')
      }

      // Upload and parse
      const result = await resumeService.uploadResume(file)
      
      // Reload resumes
      await loadResumes()
      
      // Optionally open editor with parsed data
      if (result.parsed_data) {
        // Could open editor here with parsed data
      }
    } catch (err) {
      setUploadError(err.message || 'Failed to upload resume')
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

    try {
      await resumeService.deleteResume(resumeId)
      await loadResumes()
    } catch (err) {
      setError(err.message || 'Failed to delete resume')
    }
  }

  const handleExportPDF = async (resumeId) => {
    try {
      await resumeService.exportPDF(resumeId)
    } catch (err) {
      setError(err.message || 'Failed to export PDF')
    }
  }

  const handleExportDOCX = async (resumeId) => {
    try {
      await resumeService.exportDOCX(resumeId)
    } catch (err) {
      setError(err.message || 'Failed to export DOCX')
    }
  }

  const handleCreateResume = () => {
    setShowCreateModal(true)
  }

  const handleEditResume = async (resumeId) => {
    try {
      const resume = await resumeService.getResume(resumeId)
      setEditingResume(resume)
    } catch (err) {
      setError(err.message || 'Failed to load resume')
    }
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (isGuest) {
    return (
      <div className="resumes-page-perfect">
        <div className="dashboard-header-section">
          <div className="dashboard-title-area">
            <h1 className="dashboard-main-title">Resumes</h1>
            <p className="dashboard-subtitle">Manage your resume versions and mapping</p>
          </div>
        </div>
        <div className="content-card-perfect">
          <div className="export-guest-warning">
            <IconAlertCircle />
            <span>Resume management is disabled in Guest Mode. Connect Gmail to manage resumes.</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="resumes-page-perfect">
      {/* Header Section */}
      <div className="dashboard-header-section">
        <div className="dashboard-title-area">
          <h1 className="dashboard-main-title">Resumes</h1>
          <p className="dashboard-subtitle">Manage your resume versions and mapping</p>
        </div>
        <button
          type="button"
          className="dashboard-action-btn"
          onClick={handleCreateResume}
          disabled={loading}
        >
          <IconPlus />
          <span>Create Resume</span>
        </button>
      </div>

      {error && (
        <div className="export-error">
          <IconAlertCircle />
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="error-close-btn">
            <IconX />
          </button>
        </div>
      )}

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
                  <p className="content-card-subtitle">Upload PDF or DOCX to parse and edit</p>
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
                      Drag and drop your PDF or DOCX here, or click to browse
                    </div>
                    <div className="upload-text-hint">PDF or DOCX only, max 10MB</div>
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
                  <p className="content-card-subtitle">{loading ? 'Loading...' : `${resumes.length} resume${resumes.length !== 1 ? 's' : ''}`}</p>
                </div>
              </div>
            </div>
            {loading ? (
              <div className="resumes-loading">
                <div className="upload-spinner" />
                <p>Loading resumes...</p>
              </div>
            ) : resumes.length === 0 ? (
              <div className="resumes-empty-perfect">
                <IconDocument />
                <p>No resumes yet.</p>
                <p className="resumes-empty-hint">Create a new resume or upload an existing one</p>
              </div>
            ) : (
              <div className="resumes-list-perfect">
                {resumes.map((resume) => (
                  <div key={resume.id} className="resume-item-perfect">
                    <div className="resume-item-icon">
                      <IconDocument />
                    </div>
                    <div className="resume-item-content">
                      <div className="resume-item-name">{resume.title}</div>
                      <div className="resume-item-meta">
                        <span className="resume-item-date">Updated {formatDate(resume.updated_at)}</span>
                        {resume.is_active && (
                          <>
                            <span className="resume-item-separator">•</span>
                            <span className="resume-item-active">Active</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="resume-item-actions">
                      <button
                        type="button"
                        className="resume-action-btn resume-edit-btn"
                        onClick={() => handleEditResume(resume.id)}
                        title="Edit"
                      >
                        <IconEdit />
                      </button>
                      <button
                        type="button"
                        className="resume-action-btn resume-export-pdf-btn"
                        onClick={() => handleExportPDF(resume.id)}
                        title="Export PDF"
                      >
                        <IconFileText />
                      </button>
                      <button
                        type="button"
                        className="resume-action-btn resume-export-docx-btn"
                        onClick={() => handleExportDOCX(resume.id)}
                        title="Export DOCX"
                      >
                        <IconFile />
                      </button>
                      <button
                        type="button"
                        className="resume-action-btn resume-remove-btn"
                        onClick={() => handleDeleteResume(resume.id)}
                        title="Delete"
                      >
                        <IconX />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Create Resume Modal */}
      {showCreateModal && (
        <ResumeEditor
          resume={null}
          onClose={() => setShowCreateModal(false)}
          onSave={async () => {
            await loadResumes()
            setShowCreateModal(false)
          }}
        />
      )}

      {/* Edit Resume Modal */}
      {editingResume && (
        <ResumeEditor
          resume={editingResume}
          onClose={() => setEditingResume(null)}
          onSave={async () => {
            await loadResumes()
            setEditingResume(null)
          }}
        />
      )}
    </div>
  )
}

// Resume Editor Component with Auto-save
function ResumeEditor({ resume, onClose, onSave }) {
  const { isGuest } = useAuth()
  const [title, setTitle] = useState(resume?.title || '')
  const [summary, setSummary] = useState(resume?.summary || '')
  const [experience, setExperience] = useState(resume?.experience || [])
  const [education, setEducation] = useState(resume?.education || [])
  const [skills, setSkills] = useState(resume?.skills || [])
  const [projects, setProjects] = useState(resume?.projects || [])
  const [certifications, setCertifications] = useState(resume?.certifications || [])
  const [saveStatus, setSaveStatus] = useState('saved') // 'saving', 'saved', 'error'
  const [saveError, setSaveError] = useState(null)
  const autoSaveTimeoutRef = useRef(null)

  // Auto-save with debouncing
  const autoSave = useCallback(async () => {
    if (isGuest) return

    setSaveStatus('saving')
    setSaveError(null)

    try {
      const resumeData = {
        title: title || 'Untitled Resume',
        summary,
        experience,
        education,
        skills,
        projects,
        certifications,
      }

      if (resume?.id) {
        // Update existing
        await resumeService.updateResume(resume.id, resumeData)
      } else {
        // Create new
        await resumeService.createResume(resumeData)
        onSave()
      }

      setSaveStatus('saved')
    } catch (err) {
      setSaveStatus('error')
      setSaveError(err.message || 'Failed to save')
    }
  }, [title, summary, experience, education, skills, projects, certifications, resume?.id, isGuest, onSave])

  // Debounced auto-save
  useEffect(() => {
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }

    autoSaveTimeoutRef.current = setTimeout(() => {
      if (title || summary || experience.length > 0) {
        autoSave()
      }
    }, 2000) // 2 second debounce

    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current)
      }
    }
  }, [title, summary, experience, education, skills, projects, certifications, autoSave])

  const handleAddExperience = () => {
    setExperience([...experience, {
      company: '',
      role: '',
      start_date: '',
      end_date: '',
      description: '',
    }])
  }

  const handleUpdateExperience = (index, field, value) => {
    const updated = [...experience]
    updated[index] = { ...updated[index], [field]: value }
    setExperience(updated)
  }

  const handleRemoveExperience = (index) => {
    setExperience(experience.filter((_, i) => i !== index))
  }

  const handleAddSkill = () => {
    const skill = prompt('Enter skill:')
    if (skill) {
      setSkills([...skills, skill])
    }
  }

  const handleRemoveSkill = (index) => {
    setSkills(skills.filter((_, i) => i !== index))
  }

  const handleManualSave = async () => {
    await autoSave()
  }

  return (
    <div className="resume-editor-modal" onClick={onClose}>
      <div className="resume-editor-content" onClick={(e) => e.stopPropagation()}>
        <div className="resume-editor-header">
          <div className="resume-editor-title">
            <h2>{resume ? 'Edit Resume' : 'Create Resume'}</h2>
            <div className="resume-editor-save-status">
              {saveStatus === 'saving' && (
                <span className="save-status saving">
                  <div className="upload-spinner" />
                  Saving...
                </span>
              )}
              {saveStatus === 'saved' && (
                <span className="save-status saved">
                  <IconCheck />
                  Saved
                </span>
              )}
              {saveStatus === 'error' && (
                <span className="save-status error">
                  <IconAlertCircle />
                  {saveError || 'Save failed'}
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            className="resume-editor-close"
            onClick={onClose}
            aria-label="Close editor"
          >
            <IconX />
          </button>
        </div>

        <div className="resume-editor-body">
          <div className="resume-editor-form">
            {/* Title */}
            <div className="resume-field">
              <label>Resume Title *</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Software Engineer Resume"
                className="resume-input"
              />
            </div>

            {/* Summary */}
            <div className="resume-field">
              <label>Summary</label>
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="Professional summary..."
                className="resume-textarea"
                rows={4}
              />
            </div>

            {/* Experience */}
            <div className="resume-section">
              <div className="resume-section-header">
                <h3>Experience</h3>
                <button type="button" onClick={handleAddExperience} className="resume-add-btn">
                  <IconPlus />
                  Add Experience
                </button>
              </div>
              {experience.map((exp, index) => (
                <div key={index} className="resume-entry">
                  <input
                    type="text"
                    value={exp.company || ''}
                    onChange={(e) => handleUpdateExperience(index, 'company', e.target.value)}
                    placeholder="Company"
                    className="resume-input"
                  />
                  <input
                    type="text"
                    value={exp.role || ''}
                    onChange={(e) => handleUpdateExperience(index, 'role', e.target.value)}
                    placeholder="Role"
                    className="resume-input"
                  />
                  <div className="resume-date-row">
                    <input
                      type="text"
                      value={exp.start_date || ''}
                      onChange={(e) => handleUpdateExperience(index, 'start_date', e.target.value)}
                      placeholder="Start Date"
                      className="resume-input"
                    />
                    <input
                      type="text"
                      value={exp.end_date || ''}
                      onChange={(e) => handleUpdateExperience(index, 'end_date', e.target.value)}
                      placeholder="End Date"
                      className="resume-input"
                    />
                  </div>
                  <textarea
                    value={exp.description || ''}
                    onChange={(e) => handleUpdateExperience(index, 'description', e.target.value)}
                    placeholder="Description"
                    className="resume-textarea"
                    rows={3}
                  />
                  <button
                    type="button"
                    onClick={() => handleRemoveExperience(index)}
                    className="resume-remove-entry-btn"
                  >
                    <IconX />
                  </button>
                </div>
              ))}
            </div>

            {/* Skills */}
            <div className="resume-section">
              <div className="resume-section-header">
                <h3>Skills</h3>
                <button type="button" onClick={handleAddSkill} className="resume-add-btn">
                  <IconPlus />
                  Add Skill
                </button>
              </div>
              <div className="resume-skills-list">
                {skills.map((skill, index) => (
                  <div key={index} className="resume-skill-tag">
                    {skill}
                    <button
                      type="button"
                      onClick={() => handleRemoveSkill(index)}
                      className="resume-skill-remove"
                    >
                      <IconX />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Preview */}
          <div className="resume-editor-preview">
            <h3>Preview</h3>
            <div className="resume-preview-content">
              <h2>{title || 'Untitled Resume'}</h2>
              {summary && <p>{summary}</p>}
              {experience.length > 0 && (
                <div>
                  <h3>Experience</h3>
                  {experience.map((exp, i) => (
                    <div key={i}>
                      <strong>{exp.role}</strong> at <strong>{exp.company}</strong>
                      {(exp.start_date || exp.end_date) && (
                        <span> ({exp.start_date} - {exp.end_date})</span>
                      )}
                      {exp.description && <p>{exp.description}</p>}
                    </div>
                  ))}
                </div>
              )}
              {skills.length > 0 && (
                <div>
                  <h3>Skills</h3>
                  <p>{skills.join(', ')}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="resume-editor-footer">
          <button type="button" onClick={handleManualSave} className="resume-save-btn">
            <IconCheck />
            <span>Save Now</span>
          </button>
          <button type="button" onClick={onClose} className="resume-cancel-btn">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

