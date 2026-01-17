import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import AppHeader from './AppHeader'
import '../../styles/Layout.css'

export default function MainLayout() {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="app-main-wrapper">
        <AppHeader />
        <main className="app-main-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
