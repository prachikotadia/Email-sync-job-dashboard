import { createContext, useContext, useState, useEffect } from 'react'
import { useAuth } from './AuthContext'

const ResumesContext = createContext(null)

const RESUMES_STORAGE_KEY = 'jobpulse_resumes'

export function ResumesProvider({ children }) {
  const { user } = useAuth()
  const [resumes, setResumes] = useState([])

  // Load resumes from localStorage on mount or when user changes
  useEffect(() => {
    if (user?.email) {
      const stored = localStorage.getItem(`${RESUMES_STORAGE_KEY}_${user.email}`)
      if (stored) {
        try {
          const parsed = JSON.parse(stored)
          setResumes(parsed || [])
        } catch (error) {
          console.error('Failed to parse resumes:', error)
          setResumes([])
        }
      } else {
        setResumes([])
      }
    } else {
      setResumes([])
    }
  }, [user?.email])

  const uploadResume = (file) => {
    return new Promise((resolve, reject) => {
      // Validate file type
      if (!file.type.includes('pdf') && !file.name.toLowerCase().endsWith('.pdf')) {
        reject(new Error('Only PDF files are allowed'))
        return
      }

      // Validate file size (5MB limit)
      if (file.size > 5 * 1024 * 1024) {
        reject(new Error('File size must be less than 5MB'))
        return
      }

      // Convert file to base64 for storage
      const reader = new FileReader()
      reader.onload = (e) => {
        const resumeData = {
          id: `resume_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          name: file.name,
          size: file.size,
          type: file.type,
          uploadedAt: new Date().toISOString(),
          data: e.target.result, // Base64 data
        }

        if (user?.email) {
          try {
            const updated = [...resumes, resumeData]
            setResumes(updated)
            localStorage.setItem(`${RESUMES_STORAGE_KEY}_${user.email}`, JSON.stringify(updated))
            resolve(resumeData)
          } catch (error) {
            if (error.name === 'QuotaExceededError' || error.message.includes('quota')) {
              reject(new Error('Storage limit exceeded. Please remove some resumes or use smaller files.'))
            } else {
              reject(new Error('Failed to save resume. Please try again.'))
            }
          }
        } else {
          reject(new Error('User not authenticated'))
        }
      }
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsDataURL(file)
    })
  }

  const removeResume = (id) => {
    if (user?.email) {
      const updated = resumes.filter(r => r.id !== id)
      setResumes(updated)
      localStorage.setItem(`${RESUMES_STORAGE_KEY}_${user.email}`, JSON.stringify(updated))
    }
  }

  const downloadResume = (resume) => {
    const link = document.createElement('a')
    link.href = resume.data
    link.download = resume.name
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const value = {
    resumes,
    uploadResume,
    removeResume,
    downloadResume,
  }

  return <ResumesContext.Provider value={value}>{children}</ResumesContext.Provider>
}

export function useResumes() {
  const context = useContext(ResumesContext)
  if (!context) {
    throw new Error('useResumes must be used within ResumesProvider')
  }
  return context
}
