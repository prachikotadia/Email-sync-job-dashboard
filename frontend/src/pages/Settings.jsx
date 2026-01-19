import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useAuth } from '../context/AuthContext'
import { useProfileImage } from '../context/ProfileImageContext'
import { useProfileLinks } from '../context/ProfileLinksContext'
import { IconUser, IconMail, IconSignOut, IconSettings, IconUpload, IconX, IconLinkedIn, IconGithub, IconLink, IconGlobe, IconEdit, IconTrash, IconPlus } from '../components/icons'
import { toast } from '../utils/toast'
import { validateUrl, detectPlatformFromUrl } from '../utils/urlValidator'
import '../styles/Settings.css'

// Platform options for dropdown
const PLATFORM_OPTIONS = [
  { value: 'linkedin', label: 'LinkedIn', icon: IconLinkedIn },
  { value: 'github', label: 'GitHub', icon: IconGithub },
  { value: 'portfolio', label: 'Portfolio / Website', icon: IconGlobe },
  { value: 'custom', label: 'Custom Link', icon: IconLink },
]

function Settings() {
  const { user, logout, isGuest, logoutGuest } = useAuth()
  const { profileImage, uploadProfileImage, removeProfileImage } = useProfileImage()
  const { links, loading: linksLoading, createLink, updateLink, deleteLink } = useProfileLinks()
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [showLinkModal, setShowLinkModal] = useState(false)
  const [editingLink, setEditingLink] = useState(null) // Link being edited, or null for new
  const [linkForm, setLinkForm] = useState({ type: 'linkedin', label: '', url: '' })
  const [urlValidation, setUrlValidation] = useState({ isValid: null, error: null })
  const [saving, setSaving] = useState(false)
  const fileInputRef = useRef(null)

  // Auto-detect platform when URL changes
  useEffect(() => {
    if (linkForm.url && !editingLink) {
      const detected = detectPlatformFromUrl(linkForm.url)
      if (detected && linkForm.type === 'linkedin') {
        // Only auto-detect if user hasn't manually selected a different type
        setLinkForm(prev => ({ ...prev, type: detected }))
      }
    }
  }, [linkForm.url, editingLink])

  // Real-time URL validation
  useEffect(() => {
    if (!linkForm.url) {
      setUrlValidation({ isValid: null, error: null })
      return
    }

    const validation = validateUrl(linkForm.url)
    setUrlValidation(validation)
  }, [linkForm.url])

  const handleSignOut = async () => {
    if (isGuest) {
      logoutGuest()
    } else {
      await logout()
    }
  }

  const handleImageSelect = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setUploadError(null)

    try {
      await uploadProfileImage(file)
      toast.success('Profile image uploaded successfully')
    } catch (error) {
      setUploadError(error.message)
      toast.error(error.message || 'Failed to upload image')
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleRemoveImage = () => {
    removeProfileImage()
    toast.success('Profile image removed')
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  // Open modal to add new link
  const handleAddLink = () => {
    setEditingLink(null)
    setLinkForm({ type: 'linkedin', label: '', url: '' })
    setUrlValidation({ isValid: null, error: null })
    setShowLinkModal(true)
  }

  // Open modal to edit existing link
  const handleEditLink = (link) => {
    setEditingLink(link)
    setLinkForm({
      type: link.type,
      label: link.label || '',
      url: link.url,
    })
    setUrlValidation({ isValid: true, error: null }) // Assume valid for existing links
    setShowLinkModal(true)
  }

  // Delete link
  const handleDeleteLink = async (linkId) => {
    if (!window.confirm('Are you sure you want to delete this link?')) {
      return
    }

    try {
      await deleteLink(linkId)
      toast.success('Link deleted successfully')
    } catch (error) {
      toast.error(error.message || 'Failed to delete link')
    }
  }

  // Save link (create or update)
  const handleSaveLink = async () => {
    // Validate URL
    if (!linkForm.url) {
      toast.error('URL is required')
      return
    }

    const validation = validateUrl(linkForm.url)
    if (!validation.isValid) {
      toast.error(validation.error || 'Invalid URL')
      return
    }

    // Validate label for custom type
    if (linkForm.type === 'custom' && !linkForm.label?.trim()) {
      toast.error('Label is required for custom links')
      return
    }

    setSaving(true)
    try {
      const linkData = {
        type: linkForm.type,
        url: validation.normalizedUrl,
        label: linkForm.type === 'custom' ? linkForm.label.trim() : null,
      }

      if (editingLink) {
        // Update existing link
        await updateLink(editingLink.id, linkData)
        toast.success('Link updated successfully')
      } else {
        // Create new link
        await createLink(linkData)
        toast.success('Link added successfully')
      }

      setShowLinkModal(false)
      setLinkForm({ type: 'linkedin', label: '', url: '' })
      setUrlValidation({ isValid: null, error: null })
    } catch (error) {
      const errorMessage = error.message || 'Failed to save link'
      toast.error(errorMessage)
    } finally {
      setSaving(false)
    }
  }

  // Close modal
  const handleCloseModal = () => {
    setShowLinkModal(false)
    setEditingLink(null)
    setLinkForm({ type: 'linkedin', label: '', url: '' })
    setUrlValidation({ isValid: null, error: null })
  }

  // Get icon for platform type
  const getPlatformIcon = (type) => {
    const option = PLATFORM_OPTIONS.find(opt => opt.value === type)
    return option ? option.icon : IconLink
  }

  // Truncate URL for display
  const truncateUrl = (url, maxLength = 40) => {
    if (!url) return ''
    if (url.length <= maxLength) return url
    try {
      const urlObj = new URL(url)
      const domain = urlObj.hostname
      const path = urlObj.pathname
      if (domain.length + path.length <= maxLength) {
        return `${domain}${path}`
      }
      return `${domain}${path.substring(0, maxLength - domain.length - 3)}...`
    } catch {
      return url.length > maxLength ? `${url.substring(0, maxLength - 3)}...` : url
    }
  }

  return (
    <div className="settings-page-perfect">
      {/* Header Section */}
      <div className="dashboard-header-section">
        <div className="dashboard-title-area">
          <h1 className="dashboard-main-title">Settings</h1>
          <p className="dashboard-subtitle">Manage your account and preferences</p>
        </div>
      </div>

      {/* Profile Image Section */}
      <div className="content-card-perfect settings-card-perfect">
        <div className="content-card-header">
          <div className="content-card-title-group">
            <div className="content-card-icon">
              <IconUser />
            </div>
            <div>
              <h2 className="content-card-title">Profile Picture</h2>
              <p className="content-card-subtitle">Upload your profile image</p>
            </div>
          </div>
        </div>
        <div className="settings-content">
          <div className="profile-image-upload-section">
            <div className="profile-image-preview">
              <div className="profile-image-preview-wrapper">
                {profileImage ? (
                  <img src={profileImage} alt="Profile" className="profile-image-preview-img" />
                ) : (
                  <div className="profile-image-placeholder">
                    <IconUser />
                    <span>{user?.email?.charAt(0).toUpperCase() || 'U'}</span>
                  </div>
                )}
              </div>
              {profileImage && (
                <button
                  type="button"
                  className="profile-image-remove-btn"
                  onClick={handleRemoveImage}
                  aria-label="Remove profile image"
                >
                  <IconX />
                </button>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="profile-image-input-hidden"
              id="profile-image-upload"
            />
            <div className="profile-image-actions">
              <button
                type="button"
                className="profile-image-upload-btn"
                onClick={handleUploadClick}
                disabled={uploading}
              >
                <IconUpload />
                <span>{uploading ? 'Uploading...' : profileImage ? 'Change Image' : 'Upload Image'}</span>
              </button>
              {uploadError && (
                <div className="profile-image-error">{uploadError}</div>
              )}
            </div>
            <p className="profile-image-hint">JPG, PNG or GIF. Max size 5MB.</p>
          </div>
        </div>
      </div>

      {/* Profile Links Section */}
      <div className="content-card-perfect settings-card-perfect">
        <div className="content-card-header">
          <div className="content-card-title-group">
            <div className="content-card-icon">
              <IconLink />
            </div>
            <div>
              <h2 className="content-card-title">Social Media & External Links</h2>
              <p className="content-card-subtitle">Add your professional links</p>
            </div>
          </div>
          <button
            type="button"
            className="settings-edit-btn"
            onClick={handleAddLink}
            disabled={linksLoading || isGuest}
          >
            <IconPlus />
            <span>Add Link</span>
          </button>
        </div>
        <div className="settings-content">
          {linksLoading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
              Loading links...
            </div>
          ) : links.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              <p style={{ color: '#94a3b8', marginBottom: '1rem' }}>No links added yet</p>
              <button
                type="button"
                onClick={handleAddLink}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#3b82f6',
                  color: 'white',
                  border: 'none',
                  borderRadius: '0.5rem',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  fontWeight: '500',
                }}
              >
                <IconPlus style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
                Add Your First Link
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {links.map((link) => {
                const PlatformIcon = getPlatformIcon(link.type)
                return (
                  <div
                    key={link.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem',
                      padding: '1rem',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid #334155',
                      borderRadius: '0.75rem',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.02)'
                    }}
                  >
                    <div style={{ flexShrink: 0, color: '#60a5fa' }}>
                      <PlatformIcon />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: '500', color: '#e2e8f0', marginBottom: '0.25rem' }}>
                        {link.type === 'custom' ? link.label : PLATFORM_OPTIONS.find(opt => opt.value === link.type)?.label || link.type}
                      </div>
                      <a
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          color: '#60a5fa',
                          textDecoration: 'none',
                          fontSize: '0.875rem',
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={link.url}
                      >
                        {truncateUrl(link.url)}
                      </a>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                      <button
                        type="button"
                        onClick={() => handleEditLink(link)}
                        style={{
                          padding: '0.5rem',
                          background: 'transparent',
                          border: '1px solid #475569',
                          borderRadius: '0.375rem',
                          color: '#94a3b8',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          transition: 'all 0.2s',
                        }}
                        title="Edit link"
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = '#60a5fa'
                          e.currentTarget.style.color = '#60a5fa'
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = '#475569'
                          e.currentTarget.style.color = '#94a3b8'
                        }}
                      >
                        <IconEdit />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteLink(link.id)}
                        style={{
                          padding: '0.5rem',
                          background: 'transparent',
                          border: '1px solid #475569',
                          borderRadius: '0.375rem',
                          color: '#94a3b8',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          transition: 'all 0.2s',
                        }}
                        title="Delete link"
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = '#ef4444'
                          e.currentTarget.style.color = '#ef4444'
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = '#475569'
                          e.currentTarget.style.color = '#94a3b8'
                        }}
                      >
                        <IconTrash />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Account Section */}
      <div className="content-card-perfect settings-card-perfect">
        <div className="content-card-header">
          <div className="content-card-title-group">
            <div className="content-card-icon">
              <IconMail />
            </div>
            <div>
              <h2 className="content-card-title">Account</h2>
              <p className="content-card-subtitle">Your account information</p>
            </div>
          </div>
        </div>
        <div className="settings-content">
          <div className="setting-item-perfect">
            <div className="setting-item-icon">
              <IconMail />
            </div>
            <div className="setting-item-info">
              <label className="setting-label">Email</label>
              <p className="setting-value">{user?.email || 'Not available'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Actions Section */}
      <div className="content-card-perfect settings-card-perfect">
        <div className="content-card-header">
          <div className="content-card-title-group">
            <div className="content-card-icon">
              <IconSettings />
            </div>
            <div>
              <h2 className="content-card-title">Actions</h2>
              <p className="content-card-subtitle">Account management</p>
            </div>
          </div>
        </div>
        <div className="settings-content">
          <button onClick={handleSignOut} className="settings-logout-btn">
            <IconSignOut />
            <span>Sign Out</span>
          </button>
        </div>
      </div>

      {/* Link Modal */}
      {showLinkModal && createPortal(
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
            zIndex: 1000,
            padding: '1rem',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              handleCloseModal()
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
              maxHeight: '90vh',
              overflow: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: 0, color: '#e2e8f0', fontSize: '1.5rem', fontWeight: '600' }}>
                {editingLink ? 'Edit Link' : 'Add New Link'}
              </h2>
              <button
                type="button"
                onClick={handleCloseModal}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '0.5rem',
                  display: 'flex',
                  alignItems: 'center',
                }}
                aria-label="Close modal"
              >
                <IconX />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Platform Type */}
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', color: '#e2e8f0', fontSize: '0.875rem', fontWeight: '500' }}>
                  Platform
                </label>
                <select
                  value={linkForm.type}
                  onChange={(e) => setLinkForm(prev => ({ ...prev, type: e.target.value, label: e.target.value === 'custom' ? prev.label : '' }))}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid #334155',
                    borderRadius: '0.5rem',
                    color: '#e2e8f0',
                    fontSize: '0.875rem',
                    cursor: 'pointer',
                  }}
                  disabled={saving}
                >
                  {PLATFORM_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Custom Label (only for custom type) */}
              {linkForm.type === 'custom' && (
                <div>
                  <label style={{ display: 'block', marginBottom: '0.5rem', color: '#e2e8f0', fontSize: '0.875rem', fontWeight: '500' }}>
                    Label <span style={{ color: '#ef4444' }}>*</span>
                  </label>
                  <input
                    type="text"
                    value={linkForm.label}
                    onChange={(e) => setLinkForm(prev => ({ ...prev, label: e.target.value }))}
                    placeholder="e.g., Personal Blog, Twitter, etc."
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid #334155',
                      borderRadius: '0.5rem',
                      color: '#e2e8f0',
                      fontSize: '0.875rem',
                    }}
                    disabled={saving}
                  />
                </div>
              )}

              {/* URL Input */}
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', color: '#e2e8f0', fontSize: '0.875rem', fontWeight: '500' }}>
                  URL <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="text"
                  value={linkForm.url}
                  onChange={(e) => setLinkForm(prev => ({ ...prev, url: e.target.value }))}
                  placeholder={linkForm.type === 'linkedin' ? 'linkedin.com/in/yourprofile' : linkForm.type === 'github' ? 'github.com/username' : 'example.com'}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: `1px solid ${urlValidation.isValid === false ? '#ef4444' : urlValidation.isValid === true ? '#10b981' : '#334155'}`,
                    borderRadius: '0.5rem',
                    color: '#e2e8f0',
                    fontSize: '0.875rem',
                  }}
                  disabled={saving}
                />
                {/* Real-time validation feedback */}
                {linkForm.url && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
                    {urlValidation.isValid === true && (
                      <span style={{ color: '#10b981' }}>✓ Valid URL</span>
                    )}
                    {urlValidation.isValid === false && (
                      <span style={{ color: '#ef4444' }}>{urlValidation.error}</span>
                    )}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={handleCloseModal}
                  disabled={saving}
                  style={{
                    padding: '0.75rem 1.5rem',
                    background: 'transparent',
                    border: '1px solid #475569',
                    borderRadius: '0.5rem',
                    color: '#94a3b8',
                    cursor: saving ? 'not-allowed' : 'pointer',
                    fontSize: '0.875rem',
                    fontWeight: '500',
                    opacity: saving ? 0.5 : 1,
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveLink}
                  disabled={saving || !urlValidation.isValid || (linkForm.type === 'custom' && !linkForm.label?.trim())}
                  style={{
                    padding: '0.75rem 1.5rem',
                    background: saving || !urlValidation.isValid || (linkForm.type === 'custom' && !linkForm.label?.trim()) ? '#475569' : '#3b82f6',
                    border: 'none',
                    borderRadius: '0.5rem',
                    color: 'white',
                    cursor: saving || !urlValidation.isValid || (linkForm.type === 'custom' && !linkForm.label?.trim()) ? 'not-allowed' : 'pointer',
                    fontSize: '0.875rem',
                    fontWeight: '500',
                    opacity: saving || !urlValidation.isValid || (linkForm.type === 'custom' && !linkForm.label?.trim()) ? 0.5 : 1,
                  }}
                >
                  {saving ? 'Saving...' : editingLink ? 'Update Link' : 'Add Link'}
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

export default Settings
