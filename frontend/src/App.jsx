import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import Router from './router/router'
import './styles/App.css'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Router />
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
