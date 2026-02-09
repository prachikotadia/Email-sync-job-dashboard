import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // 4xx or 5xx errors - support detail as string or object
      let message = error.response.data?.detail ?? error.response.data?.message
      if (message != null && typeof message === 'object') {
        message = message.detail ?? message.error ?? message.message ?? JSON.stringify(message).slice(0, 200)
      }
      message = (message && String(message).trim()) || 'An error occurred'
      console.error('API Error:', {
        status: error.response.status,
        message,
        url: error.config?.url,
        data: error.response.data,
      })
      
      // 401 Unauthorized - clear token and redirect
      if (error.response.status === 401) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
    } else if (error.request) {
      // Network error
      console.error('Network Error:', error.request)
    } else {
      console.error('Error:', error.message)
    }
    
    return Promise.reject(error)
  }
)

export default apiClient
