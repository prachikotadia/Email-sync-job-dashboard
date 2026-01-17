import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { exportService } from '../services/exportService'
import { gmailService } from '../services/gmailService'
import { IconDownload, IconExcel, IconFile, IconDocument, IconFileText, IconAlertCircle } from '../components/icons'
import '../styles/ExportData.css'

export default function ExportData() {
  const { user, isGuest } = useAuth()
  const [format, setFormat] = useState('xlsx')
  const [category, setCategory] = useState('ALL')
  const [dateRangeType, setDateRangeType] = useState('Last 30 days')
  const [customDateFrom, setCustomDateFrom] = useState('')
  const [customDateTo, setCustomDateTo] = useState('')
  const [fields, setFields] = useState([
    'company_name',
    'category',
    'received_at',
    'last_updated',
    'source_email',
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasData, setHasData] = useState(false)

  // Check if user has data to export
  useEffect(() => {
    if (isGuest) {
      setHasData(false)
      return
    }

    const checkData = async () => {
      try {
        const stats = await gmailService.getStats()
        const total = stats?.total || 0
        setHasData(total > 0)
      } catch (err) {
        console.error('Error checking data:', err)
        setHasData(false)
      }
    }

    checkData()
  }, [isGuest])

  const handleFieldToggle = (field) => {
    setFields((prev) =>
      prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]
    )
  }

  const getDateRange = () => {
    if (dateRangeType === 'Custom') {
      return {
        from: customDateFrom || null,
        to: customDateTo || null,
      }
    }

    const today = new Date()
    let from = null

    if (dateRangeType === 'Last 7 days') {
      from = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
    } else if (dateRangeType === 'Last 30 days') {
      from = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)
    } else if (dateRangeType === 'Last 90 days') {
      from = new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000)
    }
    // 'All time' means from = null

    return {
      from: from ? from.toISOString().split('T')[0] : null,
      to: null,
    }
  }

  const getCategoryValue = () => {
    if (category === 'All Statuses') return 'ALL'
    if (category === 'Offer') return 'OFFER'
    return category.toUpperCase()
  }

  const handleExport = async () => {
    if (!hasData && !isGuest) {
      setError('No data available to export')
      return
    }

    if (fields.length === 0) {
      setError('Please select at least one field to export')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const dateRange = getDateRange()
      const categoryValue = getCategoryValue()

      // Show progress
      console.log('Preparing export...')

      const blob = await exportService.exportApplications({
        format,
        category: categoryValue,
        dateRange,
        fields,
      })

      // Generate filename
      const timestamp = new Date().toISOString().split('T')[0].replace(/-/g, '')
      const formatExt = format === 'xlsx' ? 'xlsx' : format
      const filename = `applications_export_${timestamp}.${formatExt}`

      // Download file
      exportService.downloadFile(blob, filename)

      console.log('Download started')
    } catch (err) {
      console.error('Export error:', err)
      setError(err.message || 'Export failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const allFields = [
    { key: 'company_name', label: 'Company Name' },
    { key: 'category', label: 'Category' },
    { key: 'received_at', label: 'Received Date' },
    { key: 'last_updated', label: 'Last Updated' },
    { key: 'source_email', label: 'Source Email' },
    { key: 'gmail_message_id', label: 'Gmail Message ID' },
  ]

  return (
    <div className="export-page-perfect">
      {/* Header Section */}
      <div className="dashboard-header-section">
        <div className="dashboard-title-area">
          <h1 className="dashboard-main-title">Export Data</h1>
          <p className="dashboard-subtitle">Download your application history for analysis</p>
        </div>
      </div>

      {/* Export Card */}
      <div className="content-card-perfect export-card-perfect">
        <div className="content-card-header">
          <div className="content-card-title-group">
            <div className="content-card-icon content-card-icon-success">
              <IconDownload />
            </div>
            <div>
              <h2 className="content-card-title">Export Data</h2>
              <p className="content-card-subtitle">Download your application history</p>
            </div>
          </div>
        </div>

        {isGuest && (
          <div className="export-guest-warning">
            <IconAlertCircle />
            <span>Export is disabled in Guest Mode. Connect Gmail to export your data.</span>
          </div>
        )}

        {error && (
          <div className="export-error">
            <IconAlertCircle />
            <span>{error}</span>
          </div>
        )}

        <div className="export-form-perfect">
          {/* Format Selection */}
          <div className="export-field-perfect">
            <label className="export-label">Export Format</label>
            <div className="export-format-options">
              <button
                type="button"
                className={`export-format-btn ${format === 'csv' ? 'active' : ''}`}
                onClick={() => setFormat('csv')}
              >
                <IconFileText />
                <span>CSV</span>
              </button>
              <button
                type="button"
                className={`export-format-btn ${format === 'xlsx' ? 'active' : ''}`}
                onClick={() => setFormat('xlsx')}
              >
                <IconExcel />
                <span>Excel</span>
              </button>
              <button
                type="button"
                className={`export-format-btn ${format === 'json' ? 'active' : ''}`}
                onClick={() => setFormat('json')}
              >
                <IconFile />
                <span>JSON</span>
              </button>
              <button
                type="button"
                className={`export-format-btn ${format === 'pdf' ? 'active' : ''}`}
                onClick={() => setFormat('pdf')}
              >
                <IconDocument />
                <span>PDF</span>
              </button>
            </div>
          </div>

          {/* Category Filter */}
          <div className="export-field-perfect">
            <label htmlFor="export-category" className="export-label">Category Filter</label>
            <select
              id="export-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="export-select-perfect"
              disabled={isGuest}
            >
              <option value="All Statuses">All Applications</option>
              <option value="Applied">Applied</option>
              <option value="Rejected">Rejected</option>
              <option value="Interview">Interview</option>
              <option value="Offer">Offer / Accepted</option>
              <option value="Ghosted">Ghosted</option>
            </select>
          </div>

          {/* Date Range */}
          <div className="export-field-perfect">
            <label htmlFor="export-date-range" className="export-label">Date Range</label>
            <select
              id="export-date-range"
              value={dateRangeType}
              onChange={(e) => setDateRangeType(e.target.value)}
              className="export-select-perfect"
              disabled={isGuest}
            >
              <option value="All time">All time</option>
              <option value="Last 7 days">Last 7 days</option>
              <option value="Last 30 days">Last 30 days</option>
              <option value="Last 90 days">Last 90 days</option>
              <option value="Custom">Custom range</option>
            </select>
          </div>

          {/* Custom Date Range */}
          {dateRangeType === 'Custom' && (
            <div className="export-field-perfect export-custom-dates">
              <div className="export-date-input-group">
                <label htmlFor="export-date-from" className="export-label-small">From</label>
                <input
                  id="export-date-from"
                  type="date"
                  value={customDateFrom}
                  onChange={(e) => setCustomDateFrom(e.target.value)}
                  className="export-date-input"
                  disabled={isGuest}
                />
              </div>
              <div className="export-date-input-group">
                <label htmlFor="export-date-to" className="export-label-small">To</label>
                <input
                  id="export-date-to"
                  type="date"
                  value={customDateTo}
                  onChange={(e) => setCustomDateTo(e.target.value)}
                  className="export-date-input"
                  disabled={isGuest}
                />
              </div>
            </div>
          )}

          {/* Fields Selection */}
          <div className="export-field-perfect">
            <label className="export-label">Fields to Include</label>
            <div className="export-fields-grid">
              {allFields.map((field) => (
                <label key={field.key} className="export-field-checkbox">
                  <input
                    type="checkbox"
                    checked={fields.includes(field.key)}
                    onChange={() => handleFieldToggle(field.key)}
                    disabled={isGuest}
                  />
                  <span>{field.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleExport}
          className="export-download-btn-perfect"
          disabled={loading || isGuest || !hasData || fields.length === 0}
        >
          {loading ? (
            <>
              <div className="export-spinner" />
              <span>Generating Export...</span>
            </>
          ) : (
            <>
              <IconDownload />
              <span>Download {format.toUpperCase()} Report</span>
            </>
          )}
        </button>

        {!hasData && !isGuest && (
          <p className="export-meta-perfect export-no-data">
            No application data available. Sync your Gmail to export data.
          </p>
        )}

        {hasData && (
          <p className="export-meta-perfect">
            Export will include {fields.length} field{fields.length !== 1 ? 's' : ''} based on your filters.
          </p>
        )}
      </div>
    </div>
  )
}
