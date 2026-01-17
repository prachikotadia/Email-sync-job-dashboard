import { useState } from 'react'
import { MOCK_MISSING_CONFIRMATIONS } from '../mock/resumes.mock'
import { IconUpload, IconCheck, IconEdit } from '../components/icons'
import '../styles/Resumes.css'

export default function Resumes() {
  const [confirmations] = useState(MOCK_MISSING_CONFIRMATIONS)
  const [resumes, setResumes] = useState([])

  const handleFileChange = (e) => {
    const files = e.target.files
    if (files?.length) {
      setResumes((prev) => [...prev, ...Array.from(files)])
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const files = e.dataTransfer.files
    if (files?.length) {
      setResumes((prev) => [...prev, ...Array.from(files)])
    }
  }

  const handleDragOver = (e) => e.preventDefault()

  return (
    <div className="resumes-page">
      <div className="resumes-main">
        <div className="resumes-header">
          <h1>Resumes</h1>
          <p className="resumes-subtitle">Manage your resume versions and mapping</p>
        </div>

        <div
          className="resumes-upload"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          <input
            type="file"
            accept=".pdf"
            multiple
            onChange={handleFileChange}
            className="resumes-upload-input"
            id="resume-upload"
          />
          <label htmlFor="resume-upload" className="resumes-upload-label">
            <IconUpload />
            <span className="resumes-upload-title">Upload new resume</span>
            <span className="resumes-upload-hint">
              Drag and drop your PDF here, or click to browse
            </span>
            <span className="resumes-upload-limit">PDF only, max 5MB</span>
          </label>
        </div>

        <div className="resumes-list-section">
          <h2>Your Resumes</h2>
          <div className="resumes-list">
            {resumes.length === 0 ? (
              <p className="resumes-list-empty">No resumes uploaded yet.</p>
            ) : (
              resumes.map((f, i) => (
                <div key={i} className="resume-item">
                  <span className="resume-item-name">{f.name}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <aside className="resumes-sidebar">
        <div className="resumes-missing-card">
          <div className="resumes-missing-header">
            <span className="resumes-missing-icon">!</span>
            <h3>Missing Confirmations</h3>
          </div>
          <p className="resumes-missing-desc">
            We found {confirmations.length} applications where the resume used is unclear or low confidence.
          </p>
          <div className="resumes-missing-list">
            {confirmations.map((item) => (
              <div key={item.id} className="resumes-missing-item">
                <div className="resumes-missing-item-header">
                  <span className="resumes-missing-company">{item.company}</span>
                  <span className="resumes-missing-role">{item.role}</span>
                </div>
                <p className="resumes-missing-time">{item.timeAgo}</p>
                <div className="resumes-missing-suggestion">
                  <span className="resumes-missing-suggestion-label">AI Suggestion:</span>
                  <span className="resumes-missing-suggestion-file">{item.suggestedResume}</span>
                  <span className={`resumes-missing-confidence confidence-${item.confidence >= 90 ? 'high' : 'medium'}`}>
                    {item.confidence}%
                  </span>
                </div>
                <div className="resumes-missing-actions">
                  <button type="button" className="resumes-confirm-btn">
                    <IconCheck />
                    Confirm
                  </button>
                  <button type="button" className="resumes-edit-btn" aria-label="Edit">
                    <IconEdit />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  )
}
