import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { ProfileImageProvider } from './context/ProfileImageContext'
import { ProfileLinksProvider } from './context/ProfileLinksContext'
import { ResumesProvider } from './context/ResumesContext'
import Router from './router/router'
import './styles/App.css'

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProfileImageProvider>
          <ProfileLinksProvider>
            <ResumesProvider>
              <BrowserRouter>
                <Router />
              </BrowserRouter>
            </ResumesProvider>
          </ProfileLinksProvider>
        </ProfileImageProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
