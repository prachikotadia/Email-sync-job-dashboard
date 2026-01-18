import { createContext, useContext, useState, useEffect } from 'react'
import { useAuth } from './AuthContext'

const ProfileLinksContext = createContext(null)

const PROFILE_LINKS_STORAGE_KEY = 'jobpulse_profile_links'

const DEFAULT_LINKS = {
  linkedin: '',
  portfolio: '',
  indeed: '',
  github: '',
  website: '',
  other: '',
}

export function ProfileLinksProvider({ children }) {
  const { user } = useAuth()
  const [links, setLinks] = useState(DEFAULT_LINKS)

  // Load profile links from localStorage on mount or when user changes
  useEffect(() => {
    if (user?.email) {
      const stored = localStorage.getItem(`${PROFILE_LINKS_STORAGE_KEY}_${user.email}`)
      if (stored) {
        try {
          const parsed = JSON.parse(stored)
          setLinks({ ...DEFAULT_LINKS, ...parsed })
        } catch (error) {
          console.error('Failed to parse profile links:', error)
          setLinks(DEFAULT_LINKS)
        }
      } else {
        setLinks(DEFAULT_LINKS)
      }
    } else {
      setLinks(DEFAULT_LINKS)
    }
  }, [user?.email])

  const updateLinks = (newLinks) => {
    if (user?.email) {
      const updated = { ...links, ...newLinks }
      setLinks(updated)
      try {
        localStorage.setItem(`${PROFILE_LINKS_STORAGE_KEY}_${user.email}`, JSON.stringify(updated))
      } catch (error) {
        console.error('Failed to save profile links:', error)
        throw new Error('Failed to save links. Please try again.')
      }
    }
  }

  const resetLinks = () => {
    if (user?.email) {
      setLinks(DEFAULT_LINKS)
      localStorage.removeItem(`${PROFILE_LINKS_STORAGE_KEY}_${user.email}`)
    }
  }

  const value = {
    links,
    updateLinks,
    resetLinks,
  }

  return <ProfileLinksContext.Provider value={value}>{children}</ProfileLinksContext.Provider>
}

export function useProfileLinks() {
  const context = useContext(ProfileLinksContext)
  if (!context) {
    throw new Error('useProfileLinks must be used within ProfileLinksProvider')
  }
  return context
}
