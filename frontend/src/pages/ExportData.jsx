import { useState } from 'react'
import { IconDownload, IconExcel } from '../components/icons'
import '../styles/ExportData.css'

export default function ExportData() {
  const [dateRange, setDateRange] = useState('Last 30 days')
  const [statusFilter, setStatusFilter] = useState('All Statuses')

  const handleDownload = () => {
    // Placeholder – wire to export API when available
    console.log('Export', { dateRange, statusFilter })
  }

  return (
    <div className="export-page">
      <div className="export-header">
        <h1>Export Data</h1>
        <p className="export-subtitle">Download your application history for analysis</p>
      </div>

      <div className="export-card">
        <div className="export-card-icon">
          <IconExcel />
        </div>
        <div className="export-form">
          <div className="export-field">
            <label htmlFor="export-date">Date Range</label>
            <select
              id="export-date"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="export-select"
            >
              <option value="Last 7 days">Last 7 days</option>
              <option value="Last 30 days">Last 30 days</option>
              <option value="Last 90 days">Last 90 days</option>
              <option value="All time">All time</option>
            </select>
          </div>
          <div className="export-field">
            <label htmlFor="export-status">Status Filter</label>
            <select
              id="export-status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="export-select"
            >
              <option value="All Statuses">All Statuses</option>
              <option value="Applied">Applied</option>
              <option value="Rejected">Rejected</option>
              <option value="Interview">Interview</option>
              <option value="Offer">Offer</option>
              <option value="Ghosted">Ghosted</option>
            </select>
          </div>
        </div>
        <button type="button" onClick={handleDownload} className="export-download-btn">
          <IconDownload />
          <span>Download Excel Report</span>
        </button>
        <p className="export-meta">Includes metadata, email counts, and timeline events.</p>
      </div>
    </div>
  )
}
