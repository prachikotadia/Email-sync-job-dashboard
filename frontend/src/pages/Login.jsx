import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authService } from '../services/authService'
import { FEATURES } from '../config/features'
import '../styles/Login.css'

function Login() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const { login, isAuthenticated, loginAsGuest } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, navigate])

  // Handle OAuth callback
  useEffect(() => {
    const code = searchParams.get('code')
    if (code) {
      handleCallback(code)
    }
  }, [searchParams])

  const handleCallback = async (code) => {
    setLoading(true)
    setError(null)

    try {
      const result = await login(code)
      if (result.success) {
        navigate('/dashboard', { replace: true })
      } else {
        setError(result.error || 'Login failed')
      }
    } catch (err) {
      setError(err.message || 'An error occurred during login')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleLogin = async () => {
    setLoading(true)
    setError(null)

    try {
      const authUrl = await authService.initiateLogin()
      // Redirect to Google OAuth
      window.location.href = authUrl
    } catch (err) {
      setError(err.message || 'Failed to initiate login')
      setLoading(false)
    }
  }

  // 🚨 TEMPORARY GUEST MODE – REMOVE AFTER BACKEND STABILIZES
  const handleGuestLogin = () => {
    loginAsGuest()
    navigate('/dashboard', { replace: true })
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>JobPulse AI</h1>
          <p>Track your job applications automatically</p>
        </div>

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="login-button"
        >
          {loading ? 'Connecting...' : 'Sign in with Google'}
        </button>

        {FEATURES.GUEST_MODE_ENABLED && (
          <button
            type="button"
            onClick={handleGuestLogin}
            disabled={loading}
            className="login-button login-button-guest"
          >
            Continue as Guest
          </button>
        )}
      </div>
    </div>
  )
}

export default Login
