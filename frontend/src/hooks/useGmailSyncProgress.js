import { useState, useEffect, useRef, useCallback } from 'react'

const STORAGE_KEY_PREFIX = 'gmail_sync_progress_'

/**
 * Hook for subscribing to Gmail sync progress via SSE
 * 
 * @param {string} syncId - UUID of the sync job
 * @returns {object} { event, connected, reconnecting, error }
 */
export function useGmailSyncProgress(syncId) {
  const [event, setEvent] = useState(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [error, setError] = useState(null)
  
  const eventSourceRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const lastEventTimestampRef = useRef(null)
  
  // Reconnection backoff: 1s, 2s, 5s, 10s, max 30s
  const getReconnectDelay = (attempt) => {
    const delays = [1000, 2000, 5000, 10000, 30000]
    return delays[Math.min(attempt, delays.length - 1)]
  }
  
  // Load persisted state from localStorage
  const loadPersistedState = useCallback(() => {
    if (!syncId) return null
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${syncId}`)
      if (stored) {
        const parsed = JSON.parse(stored)
        setEvent(parsed)
        lastEventTimestampRef.current = parsed.ts
        return parsed
      }
    } catch (e) {
      console.error('Failed to load persisted state:', e)
    }
    return null
  }, [syncId])
  
  // Persist state to localStorage
  const persistState = useCallback((eventData) => {
    if (!syncId || !eventData) return
    try {
      localStorage.setItem(`${STORAGE_KEY_PREFIX}${syncId}`, JSON.stringify(eventData))
    } catch (e) {
      console.error('Failed to persist state:', e)
    }
  }, [syncId])
  
  // Connect to SSE stream
  const connect = useCallback(() => {
    if (!syncId) return
    
    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      
      // Get auth token from localStorage or cookie
      const token = localStorage.getItem('token') || document.cookie
        .split('; ')
        .find(row => row.startsWith('token='))
        ?.split('=')[1]
      
      // EventSource doesn't support custom headers, so pass token as query param
      const url = `${apiUrl}/api/gmail/sync/stream?sync_id=${syncId}${token ? `&token=${encodeURIComponent(token)}` : ''}`
      
      const eventSource = new EventSource(url, {
        withCredentials: true
      })
      
      eventSourceRef.current = eventSource
      setReconnecting(false)
      reconnectAttemptsRef.current = 0
      
      eventSource.onopen = () => {
        console.log(`SSE connected for sync ${syncId}`)
        setConnected(true)
        setError(null)
        setReconnecting(false)
      }
      
      eventSource.onmessage = (e) => {
        try {
          const eventData = JSON.parse(e.data)
          
          // Dedupe by timestamp (skip if we've seen this event)
          if (lastEventTimestampRef.current && 
              eventData.ts && 
              eventData.ts <= lastEventTimestampRef.current) {
            return
          }
          
          lastEventTimestampRef.current = eventData.ts
          setEvent(eventData)
          persistState(eventData)
          
          // If done, close connection
          if (eventData.done) {
            eventSource.close()
            setConnected(false)
          }
        } catch (err) {
          console.error('Failed to parse SSE event:', err)
        }
      }
      
      eventSource.onerror = (err) => {
        // Don't log as error if connection is already closed or done
        if (eventSource.readyState === EventSource.CLOSED) {
          // Connection was closed - check if it was intentional
          if (event && event.done) {
            // Sync is done, don't reconnect
            setConnected(false)
            return
          }
        }
        
        console.warn('SSE connection error, readyState:', eventSource.readyState)
        setConnected(false)
        
        // Close the connection
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }
        
        // Only reconnect if not done and not already reconnecting
        if (event && !event.done && !reconnecting) {
          setReconnecting(true)
          const delay = getReconnectDelay(reconnectAttemptsRef.current)
          reconnectAttemptsRef.current++
          
          // Prevent rapid reconnection loops - minimum 2 second delay
          const minDelay = Math.max(delay, 2000)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!event || !event.done) {
              connect()
            } else {
              setReconnecting(false)
            }
          }, minDelay)
        } else if (event && event.done) {
          // Sync is done, stop reconnecting
          setReconnecting(false)
        }
      }
      
    } catch (err) {
      console.error('Failed to create EventSource:', err)
      setError(err.message)
      setConnected(false)
    }
  }, [syncId, event, persistState])
  
  // Initial load and connect
  useEffect(() => {
    if (!syncId) {
      // Clean up if syncId is cleared
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      setConnected(false)
      setReconnecting(false)
      return
    }
    
    // Load persisted state first
    loadPersistedState()
    
    // Small delay before connecting to avoid rapid reconnection loops
    const connectTimeout = setTimeout(() => {
      connect()
    }, 100)
    
    // Cleanup on unmount
    return () => {
      clearTimeout(connectTimeout)
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      setConnected(false)
      setReconnecting(false)
    }
  }, [syncId]) // Remove connect and loadPersistedState from dependencies to prevent loops
  
  // Manual reconnect function
  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0
    connect()
  }, [connect])
  
  return {
    event,
    connected,
    reconnecting,
    error,
    reconnect
  }
}
