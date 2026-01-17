import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { IconGrid, IconBuilding, IconDocument, IconDownload, IconSettings, IconSignOut } from '../icons'

export default function Sidebar() {
  const { user, logout, isGuest, logoutGuest } = useAuth()
  const navigate = useNavigate()

  const handleSignOut = async () => {
    if (isGuest) {
      logoutGuest()
    } else {
      await logout()
    }
    navigate('/login', { replace: true })
  }

  const navItems = [
    { to: '/dashboard', icon: IconGrid, label: 'Dashboard' },
    { to: '/applications', icon: IconBuilding, label: 'Applications' },
    { to: '/resumes', icon: IconDocument, label: 'Resumes' },
    { to: '/export', icon: IconDownload, label: 'Export Data' },
    { to: '/settings', icon: IconSettings, label: 'Settings' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="sidebar-logo-icon">JP</span>
        <span className="sidebar-logo-text">JobPulse</span>
      </div>

      <nav className="sidebar-nav">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `sidebar-nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button type="button" onClick={handleSignOut} className="sidebar-signout">
          <IconSignOut />
          <span>Sign Out</span>
        </button>
        <p className="sidebar-email">{user?.email || 'Not signed in'}</p>
      </div>
    </aside>
  )
}
