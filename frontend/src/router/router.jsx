import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import MainLayout from '../components/layout/MainLayout'
import Login from '../pages/Login'
import Dashboard from '../pages/Dashboard'
import Applications from '../pages/Applications'
import Resumes from '../pages/Resumes'
import ExportData from '../pages/ExportData'
import Settings from '../pages/Settings'

function PrivateRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="app-loading" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: '#94a3b8' }}>
        Loading...
      </div>
    )
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function Router() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <MainLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="applications" element={<Applications />} />
        <Route path="resumes" element={<Resumes />} />
        <Route path="export" element={<ExportData />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default Router
