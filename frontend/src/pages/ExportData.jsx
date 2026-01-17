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
              <IconExcel />
            </div>
            <div>
              <h2 className="content-card-title">Export to Excel</h2>
              <p className="content-card-subtitle">Generate comprehensive reports</p>
            </div>
          </div>
        </div>

        <div className="export-form-perfect">
          <div className="export-field-perfect">
            <label htmlFor="export-date" className="export-label">Date Range</label>
            <select
              id="export-date"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="export-select-perfect"
            >
              <option value="Last 7 days">Last 7 days</option>
              <option value="Last 30 days">Last 30 days</option>
              <option value="Last 90 days">Last 90 days</option>
              <option value="All time">All time</option>
            </select>
          </div>
          <div className="export-field-perfect">
            <label htmlFor="export-status" className="export-label">Status Filter</label>
            <select
              id="export-status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="export-select-perfect"
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

        <button type="button" onClick={handleDownload} className="export-download-btn-perfect">
          <IconDownload />
          <span>Download Excel Report</span>
        </button>

        <p className="export-meta-perfect">
          Includes metadata, email counts, and timeline events.
        </p>
      </div>
    </div>
  )
}
