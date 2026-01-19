import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import { IconWifi, IconSun, IconMoon, IconRefresh, IconBell } from '../icons'

export default function AppHeader() {
  const { user, isGuest } = useAuth()
  const { theme, toggleTheme, isDark } = useTheme()

  const initial = user?.email
    ? user.email.charAt(0).toUpperCase()
    : '?'

  return (
    <header className="app-header">
      <div className="app-header-actions">
        <span className={`app-header-status ${isGuest ? 'guest' : 'connected'}`}>
          <IconWifi />
          {isGuest ? 'Guest' : 'Connected'}
        </span>
        <button 
          type="button" 
          className="app-header-icon-btn" 
          aria-label="Toggle theme"
          onClick={toggleTheme}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDark ? <IconSun /> : <IconMoon />}
        </button>
        <button type="button" className="app-header-icon-btn" aria-label="Refresh">
          <IconRefresh />
        </button>
        <button type="button" className="app-header-icon-btn" aria-label="Notifications">
          <IconBell />
        </button>
        <div className="app-header-avatar" title={user?.email}>
          {initial}
        </div>
      </div>
    </header>
  )
}
