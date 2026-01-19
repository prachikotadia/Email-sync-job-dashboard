import { useState } from 'react'
import { createPortal } from 'react-dom'
import { IconX, IconCheck, IconCalendar, IconInfo } from './icons'
import '../styles/SyncOptionsModal.css'

/**
 * SyncOptionsModal - Modal for selecting sync time range
 * 
 * MANDATORY FLOW:
 * - User MUST select ONE option
 * - Sync MUST NOT start without confirmation
 * - Button text: "Done & Sync"
 * - Selected option MUST be displayed during sync
 */
export default function SyncOptionsModal({ isOpen, onClose, onConfirm }) {
  const [selectedOption, setSelectedOption] = useState('full')
  const [showWarning, setShowWarning] = useState(false)

  if (!isOpen) return null

  const options = [
    { value: '3m', label: 'Last 3 months', months: 3 },
    { value: '6m', label: 'Last 6 months', months: 6 },
    { value: '12m', label: 'Last 12 months', months: 12 },
    { value: '16m', label: 'Last 16 months', months: 16 },
    { value: 'full', label: 'Full history', months: null }
  ]

  const handleOptionChange = (value) => {
    setSelectedOption(value)
    if (value === 'full') {
      setShowWarning(true)
    } else {
      setShowWarning(false)
    }
  }

  const handleConfirm = () => {
    const option = options.find(opt => opt.value === selectedOption)
    onConfirm({
      range: selectedOption,
      months: option.months,
      label: option.label
    })
    onClose()
  }

  const modalContent = (
    <div className="sync-options-modal-overlay" onClick={onClose}>
      <div className="sync-options-modal neo-card" onClick={(e) => e.stopPropagation()}>
        <div className="sync-options-modal-header">
          <h2>Select Sync Range</h2>
          <button className="sync-options-modal-close" onClick={onClose} aria-label="Close">
            <IconX />
          </button>
        </div>

        <div className="sync-options-modal-content">
          <p className="sync-options-description">
            Choose how much email history to sync. This will scan your Gmail inbox for job-related emails.
          </p>

          <div className="sync-options-list">
            {options.map((option) => (
              <label
                key={option.value}
                className={`sync-option-item ${selectedOption === option.value ? 'selected' : ''}`}
              >
                <input
                  type="radio"
                  name="sync-range"
                  value={option.value}
                  checked={selectedOption === option.value}
                  onChange={() => handleOptionChange(option.value)}
                />
                <div className="sync-option-content">
                  <div className="sync-option-label">
                    <IconCalendar className="sync-option-icon" />
                    <span>{option.label}</span>
                  </div>
                  {option.value === 'full' && (
                    <div className="sync-option-warning">
                      <IconInfo className="sync-option-warning-icon" />
                      <span>May take longer for large inboxes</span>
                    </div>
                  )}
                </div>
                {selectedOption === option.value && (
                  <IconCheck className="sync-option-check" />
                )}
              </label>
            ))}
          </div>

          {showWarning && (
            <div className="sync-options-warning-box">
              <IconInfo className="sync-options-warning-icon" />
              <div>
                <strong>Full History Sync</strong>
                <p>
                  This will scan your entire Gmail inbox. For large inboxes (10,000+ emails), 
                  this may take 30-60 minutes or longer. Progress will be shown in real-time.
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="sync-options-modal-actions">
          <button
            type="button"
            className="sync-options-modal-btn-secondary"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="sync-options-modal-btn-primary"
            onClick={handleConfirm}
          >
            Done & Sync
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}
