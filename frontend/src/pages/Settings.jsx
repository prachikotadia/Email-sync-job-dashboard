import { useState, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { useProfileImage } from '../context/ProfileImageContext'
import { useProfileLinks } from '../context/ProfileLinksContext'
import { IconUser, IconMail, IconSignOut, IconSettings, IconUpload, IconX, IconLinkedIn, IconGithub, IconLink, IconGlobe, IconEdit } from '../components/icons'
import '../styles/Settings.css'

function Settings() {
  const { user, logout, isGuest, logoutGuest } = useAuth()
  const { profileImage, uploadProfileImage, removeProfileImage } = useProfileImage()
  const { links, updateLinks } = useProfileLinks()
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [editingLinks, setEditingLinks] = useState(false)
  const [linkForm, setLinkForm] = useState(links)
  const [linkError, setLinkError] = useState(null)
  const fileInputRef = useRef(null)

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
    } catch (error) {
      setUploadError(error.message)
    } finally {
      setUploading(false)
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const handleRemoveImage = () => {
    removeProfileImage()
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleLinkChange = (platform, value) => {
    setLinkForm(prev => ({
      ...prev,
      [platform]: value
    }))
    setLinkError(null)
  }

  const handleSaveLinks = () => {
    try {
      updateLinks(linkForm)
      setEditingLinks(false)
      setLinkError(null)
    } catch (error) {
      setLinkError(error.message)
    }
  }

  const handleCancelEdit = () => {
    setLinkForm(links)
    setEditingLinks(false)
    setLinkError(null)
  }

  const handleEditLinks = () => {
    setLinkForm(links)
    setEditingLinks(true)
  }

  const formatUrl = (url) => {
    if (!url) return ''
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url
    }
    return `https://${url}`
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
              <h2 className="content-card-title">Profile Links</h2>
              <p className="content-card-subtitle">Add your professional links</p>
            </div>
          </div>
          {!editingLinks && (
            <button
              type="button"
              className="settings-edit-btn"
              onClick={handleEditLinks}
            >
              <IconEdit />
              <span>Edit</span>
            </button>
          )}
        </div>
        <div className="settings-content">
          {linkError && (
            <div className="settings-error">{linkError}</div>
          )}
          <div className="profile-links-form">
            <div className="profile-link-field">
              <label className="profile-link-label">
                <IconLinkedIn />
                <span>LinkedIn</span>
              </label>
              {editingLinks ? (
                <input
                  type="text"
                  value={linkForm.linkedin}
                  onChange={(e) => handleLinkChange('linkedin', e.target.value)}
                  placeholder="linkedin.com/in/yourprofile"
                  className="profile-link-input"
                />
              ) : (
                <div className="profile-link-display">
                  {links.linkedin ? (
                    <a 
                      href={formatUrl(links.linkedin)} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="profile-link-value"
                    >
                      {links.linkedin}
                    </a>
                  ) : (
                    <span className="profile-link-empty">Not set</span>
                  )}
                </div>
              )}
            </div>

            <div className="profile-link-field">
              <label className="profile-link-label">
                <IconGlobe />
                <span>Portfolio</span>
              </label>
              {editingLinks ? (
                <input
                  type="text"
                  value={linkForm.portfolio}
                  onChange={(e) => handleLinkChange('portfolio', e.target.value)}
                  placeholder="yourportfolio.com"
                  className="profile-link-input"
                />
              ) : (
                <div className="profile-link-display">
                  {links.portfolio ? (
                    <a 
                      href={formatUrl(links.portfolio)} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="profile-link-value"
                    >
                      {links.portfolio}
                    </a>
                  ) : (
                    <span className="profile-link-empty">Not set</span>
                  )}
                </div>
              )}
            </div>

            <div className="profile-link-field">
              <label className="profile-link-label">
                <IconLink />
                <span>Indeed</span>
              </label>
              {editingLinks ? (
                <input
                  type="text"
                  value={linkForm.indeed}
                  onChange={(e) => handleLinkChange('indeed', e.target.value)}
                  placeholder="profile.indeed.com/..."
                  className="profile-link-input"
                />
              ) : (
                <div className="profile-link-display">
                  {links.indeed ? (
                    <a 
                      href={formatUrl(links.indeed)} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="profile-link-value"
                    >
                      {links.indeed}
                    </a>
                  ) : (
                    <span className="profile-link-empty">Not set</span>
                  )}
                </div>
              )}
            </div>

            <div className="profile-link-field">
              <label className="profile-link-label">
                <IconGithub />
                <span>GitHub</span>
              </label>
              {editingLinks ? (
                <input
                  type="text"
                  value={linkForm.github}
                  onChange={(e) => handleLinkChange('github', e.target.value)}
                  placeholder="github.com/username"
                  className="profile-link-input"
                />
              ) : (
                <div className="profile-link-display">
                  {links.github ? (
                    <a 
                      href={formatUrl(links.github)} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="profile-link-value"
                    >
                      {links.github}
                    </a>
                  ) : (
                    <span className="profile-link-empty">Not set</span>
                  )}
                </div>
              )}
            </div>

            <div className="profile-link-field">
              <label className="profile-link-label">
                <IconGlobe />
                <span>Website</span>
              </label>
              {editingLinks ? (
                <input
                  type="text"
                  value={linkForm.website}
                  onChange={(e) => handleLinkChange('website', e.target.value)}
                  placeholder="yourwebsite.com"
                  className="profile-link-input"
                />
              ) : (
                <div className="profile-link-display">
                  {links.website ? (
                    <a 
                      href={formatUrl(links.website)} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="profile-link-value"
                    >
                      {links.website}
                    </a>
                  ) : (
                    <span className="profile-link-empty">Not set</span>
                  )}
                </div>
              )}
            </div>

            <div className="profile-link-field">
              <label className="profile-link-label">
                <IconLink />
                <span>Other</span>
              </label>
              {editingLinks ? (
                <input
                  type="text"
                  value={linkForm.other}
                  onChange={(e) => handleLinkChange('other', e.target.value)}
                  placeholder="Any other platform link"
                  className="profile-link-input"
                />
              ) : (
                <div className="profile-link-display">
                  {links.other ? (
                    <a 
                      href={formatUrl(links.other)} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="profile-link-value"
                    >
                      {links.other}
                    </a>
                  ) : (
                    <span className="profile-link-empty">Not set</span>
                  )}
                </div>
              )}
            </div>
          </div>

          {editingLinks && (
            <div className="profile-links-actions">
              <button
                type="button"
                className="profile-links-save-btn"
                onClick={handleSaveLinks}
              >
                Save Changes
              </button>
              <button
                type="button"
                className="profile-links-cancel-btn"
                onClick={handleCancelEdit}
              >
                Cancel
              </button>
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
    </div>
  )
}

export default Settings
