import '../styles/StatsOverview.css'

function StatsOverview({ stats }) {
  if (!stats) {
    return (
      <div className="stats-overview">
        <h2>Statistics</h2>
        <p>No data available. Start a sync to see statistics.</p>
      </div>
    )
  }

  const {
    total = 0,
    applied = 0,
    rejected = 0,
    interview = 0,
    offer = 0,
    accepted = 0,
    ghosted = 0,
  } = stats

  return (
    <div className="stats-overview">
      <h2>Statistics</h2>
      
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Applications</div>
          <div className="stat-value">{total.toLocaleString()}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Applied</div>
          <div className="stat-value">{applied.toLocaleString()}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Rejected</div>
          <div className="stat-value">{rejected.toLocaleString()}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Interview</div>
          <div className="stat-value">{interview.toLocaleString()}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Offer</div>
          <div className="stat-value">{offer.toLocaleString()}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Accepted</div>
          <div className="stat-value">{accepted.toLocaleString()}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Ghosted</div>
          <div className="stat-value">{ghosted.toLocaleString()}</div>
        </div>
      </div>

      {stats.warning && (
        <div className="stats-warning">
          ⚠️ {stats.warning}
        </div>
      )}
    </div>
  )
}

export default StatsOverview
