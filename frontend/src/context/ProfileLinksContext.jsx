import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useAuth } from './AuthContext'
import { profileService } from '../services/profileService'

const ProfileLinksContext = createContext(null)

export function ProfileLinksProvider({ children }) {
  const { user, isGuest } = useAuth()
  const [links, setLinks] = useState([]) // Array of link objects from backend
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Load profile links from backend API
  const loadLinks = useCallback(async () => {
    if (isGuest || !user?.email) {
      setLinks([])
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await profileService.getLinks()
      setLinks(response.links || [])
    } catch (err) {
      console.error('Failed to load profile links:', err)
      setError(err.message || 'Failed to load links')
      setLinks([])
    } finally {
      setLoading(false)
    }
  }, [user?.email, isGuest])

  // Load links on mount and when user changes
  useEffect(() => {
    loadLinks()
  }, [loadLinks])

  // Create a new link
  const createLink = useCallback(async (linkData) => {
    if (isGuest || !user?.email) {
      throw new Error('Must be logged in to create links')
    }

    try {
      setError(null)
      const newLink = await profileService.createLink(linkData)
      setLinks(prev => [...prev, newLink])
      return newLink
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to create link'
      setError(errorMessage)
      throw new Error(errorMessage)
    }
  }, [user?.email, isGuest])

  // Update an existing link
  const updateLink = useCallback(async (linkId, linkData) => {
    if (isGuest || !user?.email) {
      throw new Error('Must be logged in to update links')
    }

    try {
      setError(null)
      const updatedLink = await profileService.updateLink(linkId, linkData)
      setLinks(prev => prev.map(link => link.id === linkId ? updatedLink : link))
      return updatedLink
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to update link'
      setError(errorMessage)
      throw new Error(errorMessage)
    }
  }, [user?.email, isGuest])

  // Delete a link
  const deleteLink = useCallback(async (linkId) => {
    if (isGuest || !user?.email) {
      throw new Error('Must be logged in to delete links')
    }

    try {
      setError(null)
      await profileService.deleteLink(linkId)
      setLinks(prev => prev.filter(link => link.id !== linkId))
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to delete link'
      setError(errorMessage)
      throw new Error(errorMessage)
    }
  }, [user?.email, isGuest])

  // Legacy compatibility: Convert array to object format for old components
  const linksObject = links.reduce((acc, link) => {
    if (link.type === 'linkedin') acc.linkedin = link.url
    else if (link.type === 'github') acc.github = link.url
    else if (link.type === 'portfolio') acc.portfolio = link.url
    else if (link.type === 'custom') acc.other = link.url
    return acc
  }, { linkedin: '', portfolio: '', indeed: '', github: '', website: '', other: '' })

  const value = {
    links, // Array format (new)
    linksObject, // Object format (legacy compatibility)
    loading,
    error,
    loadLinks,
    createLink,
    updateLink,
    deleteLink,
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
