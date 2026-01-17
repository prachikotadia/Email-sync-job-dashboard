import { useAuth } from '../context/AuthContext'
import '../styles/Settings.css'

function Settings() {
  const { user, logout, isGuest, logoutGuest } = useAuth()

  const handleSignOut = async () => {
    if (isGuest) {
      logoutGuest()
    } else {
      await logout()
    }
  }

  return (
    <div className="settings">
      <h1>Settings</h1>
      
      <div className="settings-section">
        <h2>Account</h2>
        <div className="setting-item">
          <label>Email</label>
          <p>{user?.email || 'Not available'}</p>
        </div>
      </div>

      <div className="settings-section">
        <h2>Actions</h2>
        <button onClick={handleSignOut} className="logout-button">
          Sign Out
        </button>
      </div>
    </div>
  )
}

export default Settings
