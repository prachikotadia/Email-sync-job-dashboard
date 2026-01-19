import { memo } from 'react'
import { IconBriefcase, IconCopy, IconExternalLink } from './icons'
import ResumeSelector from './ResumeSelector'

// Category mapping
const CATEGORY_LABELS = {
  APPLIED: 'Applied',
  REJECTED: 'Rejected',
  INTERVIEW: 'Interview',
  OFFER_ACCEPTED: 'Offer / Accepted',
  GHOSTED: 'Ghosted',
}

// Normalize category for display
const normalizeCategory = (category) => {
  if (!category) return null
  const cat = category.toUpperCase()
  if (cat === 'ACCEPTED' || cat === 'OFFER') return 'OFFER_ACCEPTED'
  return cat
}

// Get category label
const getCategoryLabel = (category) => {
  const normalized = normalizeCategory(category)
  return CATEGORY_LABELS[normalized] || category || 'Unknown'
}

// Format date
const formatDate = (dateString) => {
  if (!dateString) return '—'
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return '—'
  }
}

/**
 * Memoized ApplicationRow component for performance
 * Prevents unnecessary re-renders when parent state changes
 */
const ApplicationRow = memo(({ 
  app, 
  style, 
  onApplicationClick, 
  onCopyLink, 
  copySuccess,
  applicationResume,
  allResumes,
  onResumeChange,
  onResumesChange,
  isGuest
}) => {
  const category = normalizeCategory(app.category)
  const categoryLabel = getCategoryLabel(app.category)
  const hasGmailLink = app.gmail_deep_link || app.gmail_web_url || app.gmail_message_id

  return (
    <div style={{ ...style, padding: '0.5rem 0', boxSizing: 'border-box' }}>
      <div
        className="application-item-perfect application-item-clickable"
        onClick={() => onApplicationClick(app)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onApplicationClick(app)
          }
        }}
        title="Click to open in Gmail"
        style={{ margin: 0, width: '100%' }}
      >
        <div className="application-item-icon">
          <IconBriefcase />
        </div>
        <div className="application-item-info">
          <div className="application-company">{app.company_name || 'Unknown Company'}</div>
          {app.role && (
            <div style={{ 
              fontSize: '0.875rem', 
              fontWeight: '600', 
              color: 'var(--text-muted)',
              marginBottom: '0.25rem',
              letterSpacing: '-0.01em',
            }}>
              {app.role}
            </div>
          )}
          <div className="application-meta">
            {app.received_at && (
              <span className="application-date" style={{ 
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
              }}>
                <span style={{ fontSize: '0.75rem' }}>📅</span>
                {formatDate(app.received_at)}
              </span>
            )}
            {app.received_at && <span className="application-separator">•</span>}
            <span className="application-source">
              <span style={{ fontSize: '0.75rem', marginRight: '0.25rem' }}>📧</span>
              Source: Gmail
            </span>
          </div>
        </div>
        <div className="application-item-right">
          {/* Resume Selector */}
          <div style={{ 
            width: '100%',
            maxWidth: '220px',
            marginBottom: '0.5rem',
          }}>
            <ResumeSelector
              applicationId={app.id}
              currentResumeId={applicationResume?.resume_id || null}
              onResumeChange={(resumeId) => onResumeChange(app.id, resumeId)}
              disabled={isGuest}
              resumes={allResumes}
              onResumesChange={onResumesChange}
            />
          </div>
          
          {/* Status Badge and Actions */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.5rem',
            flexWrap: 'nowrap',
            marginTop: '0.5rem',
          }}>
            <div 
              className={`activity-status activity-status-${(category || 'UNKNOWN').toLowerCase()}`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.375rem',
              }}
            >
              <span style={{ fontSize: '0.875rem' }}>
                {category === 'APPLIED' && '📝'}
                {category === 'INTERVIEW' && '💼'}
                {category === 'OFFER_ACCEPTED' && '🎉'}
                {category === 'REJECTED' && '❌'}
                {category === 'GHOSTED' && '👻'}
                {!['APPLIED', 'INTERVIEW', 'OFFER_ACCEPTED', 'REJECTED', 'GHOSTED'].includes(category) && '📋'}
              </span>
              {categoryLabel}
            </div>
            <button
              type="button"
              onClick={(e) => onCopyLink(app, e)}
              disabled={!hasGmailLink}
              className="copy-link-btn"
              title={
                copySuccess === app.id
                  ? 'Copied!'
                  : !hasGmailLink
                  ? 'Email link unavailable'
                  : 'Copy Gmail link'
              }
              style={{
                background: 'transparent',
                border: 'none',
                cursor: !hasGmailLink ? 'not-allowed' : 'pointer',
                padding: '0.375rem',
                color: copySuccess === app.id ? '#10b981' : !hasGmailLink ? '#475569' : '#94a3b8',
                opacity: !hasGmailLink ? 0.5 : 1,
                transition: 'color 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '0.25rem',
              }}
              onMouseEnter={(e) => {
                if (hasGmailLink) {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              <IconCopy />
            </button>
            <IconExternalLink 
              className="application-gmail-link-icon"
              style={{ cursor: 'pointer' }}
              onClick={(e) => {
                e.stopPropagation()
                onApplicationClick(app)
              }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}, (prevProps, nextProps) => {
  // Custom comparison function for memo
  // Only re-render if these props change
  return (
    prevProps.app.id === nextProps.app.id &&
    prevProps.app.category === nextProps.app.category &&
    prevProps.copySuccess === nextProps.copySuccess &&
    prevProps.applicationResume?.resume_id === nextProps.applicationResume?.resume_id &&
    prevProps.allResumes.length === nextProps.allResumes.length &&
    prevProps.style === nextProps.style
  )
})

ApplicationRow.displayName = 'ApplicationRow'

export default ApplicationRow
