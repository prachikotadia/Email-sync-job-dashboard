import { useState, useEffect, useRef, useCallback } from 'react'
import { gmailService } from '../services/gmailService'

const STORAGE_KEY_PREFIX = 'gmail_sync_progress_'

/**
 * Hook for subscribing to Gmail sync progress via SSE
 * 
 * FRONTEND STATELESS BEHAVIOR RULES:
 * - On refresh: Reconnect to SSE, Fetch sync status, Resume progress display
 * - Sync paused: Show paused status message
 * - Rate limited: Show rate limit message with retry countdown
 * - Backend restarted: Auto-reconnect with status display
 * - Browser refreshed: Fetch status from backend, reconnect SSE, show last progress
 * 
 * @param {string} syncId - UUID of the sync job
 * @returns {object} { event, connected, reconnecting, error, syncStatus }
 */
export function useGmailSyncProgress(syncId) {
  const [event, setEvent] = useState(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [error, setError] = useState(null)
  const [syncStatus, setSyncStatus] = useState(null)  // Backend sync status
  
  const eventSourceRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)
  const lastEventTimestampRef = useRef(null)
  const fetchStatusInProgressRef = useRef(false)  // Prevent concurrent fetchSyncStatus calls
  const eventRef = useRef(null)  // Use ref to avoid stale closures in connect
  const connectRef = useRef(null)  // Store latest connect function
  const fetchSyncStatusRef = useRef(null)  // Store latest fetchSyncStatus function
  const loadPersistedStateRef = useRef(null)  // Store latest loadPersistedState function
  const eventBatchRef = useRef([])  // Batch SSE events to prevent UI freeze
  const batchTimeoutRef = useRef(null)  // Timeout for batch flush
  const lastUpdateTimeRef = useRef(0)  // Last UI update time for throttling
  
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
        eventRef.current = parsed  // Update ref
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
      
      // Batch/throttle SSE events to prevent UI freeze on high-frequency updates
      const THROTTLE_MS = 100 // Update UI at most every 100ms (10 updates/sec max)
      
      const flushEventBatch = () => {
        if (eventBatchRef.current.length === 0) return
        
        // Get the latest event (most recent)
        const latestEvent = eventBatchRef.current[eventBatchRef.current.length - 1]
        eventBatchRef.current = []
        
        // Update ref and state
        lastEventTimestampRef.current = latestEvent.ts
        eventRef.current = latestEvent
        setEvent(latestEvent)
        persistState(latestEvent)
        
        // If done, close connection
        if (latestEvent.done) {
          eventSource.close()
          setConnected(false)
        }
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
          
          // Add log entry to event if log_message is present
          if (eventData.log_message) {
            // Add to logs array for UI display
            if (!eventData.logs) {
              eventData.logs = []
            }
            eventData.logs.push({
              time: eventData.ts || new Date().toISOString(),
              message: eventData.log_message,
              type: eventData.log_type || eventData.level || 'info',
              email_id: eventData.email_id,
              retry_count: eventData.retry_count,
              retry_after_seconds: eventData.retry_after_seconds
            })
          }
          
          // Add to batch
          eventBatchRef.current.push(eventData)
          
          // Throttle: Only update UI every THROTTLE_MS (but allow more frequent for real-time feel)
          // Reduce throttle to 50ms for more real-time updates during active syncing
          const THROTTLE_MS_REALTIME = 50  // 20 updates/sec for real-time feel
          const now = Date.now()
          const timeSinceLastUpdate = now - lastUpdateTimeRef.current
          
          if (timeSinceLastUpdate >= THROTTLE_MS_REALTIME) {
            // Update immediately
            flushEventBatch()
            lastUpdateTimeRef.current = now
          } else {
            // Schedule batch flush
            if (batchTimeoutRef.current) {
              clearTimeout(batchTimeoutRef.current)
            }
            batchTimeoutRef.current = setTimeout(() => {
              flushEventBatch()
              lastUpdateTimeRef.current = Date.now()
            }, THROTTLE_MS_REALTIME - timeSinceLastUpdate)
          }
        } catch (err) {
          console.error('Failed to parse SSE event:', err)
        }
      }
      
      eventSource.onerror = (err) => {
        // Use ref to get current event value (avoids stale closure)
        const currentEvent = eventRef.current
        
        // Don't log as error if connection is already closed or done
        if (eventSource.readyState === EventSource.CLOSED) {
          // Connection was closed - check if it was intentional
          if (currentEvent && currentEvent.done) {
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
        // Use ref to avoid stale closure
        if (currentEvent && !currentEvent.done && !reconnecting) {
          setReconnecting(true)
          const delay = getReconnectDelay(reconnectAttemptsRef.current)
          reconnectAttemptsRef.current++
          
          // Prevent rapid reconnection loops - minimum 2 second delay
          const minDelay = Math.max(delay, 2000)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            // Check ref again (most current value)
            const latestEvent = eventRef.current
            if (!latestEvent || !latestEvent.done) {
              connect()
            } else {
              setReconnecting(false)
            }
          }, minDelay)
        } else if (currentEvent && currentEvent.done) {
          // Sync is done, stop reconnecting
          setReconnecting(false)
        }
      }
      
    } catch (err) {
      console.error('Failed to create EventSource:', err)
      setError(err.message)
      setConnected(false)
    }
  }, [syncId, persistState])  // Removed 'event' from deps to avoid TDZ and stale closures - use eventRef instead
  
  // Fetch sync status from backend (stateless behavior - on refresh/load)
  const fetchSyncStatus = useCallback(async () => {
    if (!syncId) return
    
    // Prevent concurrent calls - if already fetching, skip
    if (fetchStatusInProgressRef.current) {
      return
    }
    
    fetchStatusInProgressRef.current = true
    try {
      const status = await gmailService.getSyncStatus(syncId)
      setSyncStatus(status)
      
      // If backend has status, use it to update event if no event exists yet
      // This ensures we show progress immediately on refresh
      setEvent(prevEvent => {
        if (prevEvent) {
          eventRef.current = prevEvent  // Update ref
          return prevEvent  // Keep existing event if present
        }
        
        // Create event-like object from status for consistency
        const statusEvent = {
          sync_id: syncId,
          phase: status.state?.toLowerCase() || status.status?.toLowerCase() || 'unknown',
          status: status.status,
          message: status.message || `Sync ${status.status || 'running'}`,
          counts: status.counts || {},
          done: status.status === 'completed' || status.status === 'failed',
          ts: Date.now()
        }
        eventRef.current = statusEvent  // Update ref
        persistState(statusEvent)
        return statusEvent
      })
    } catch (err) {
      console.warn('Failed to fetch sync status:', err)
      // Don't set error - allow SSE to handle reconnection
    } finally {
      fetchStatusInProgressRef.current = false
    }
  }, [syncId, persistState])

  // Update refs immediately after callbacks are created (synchronous, not in useEffect)
  // This ensures refs are always up-to-date before any useEffect runs
  connectRef.current = connect
  fetchSyncStatusRef.current = fetchSyncStatus
  loadPersistedStateRef.current = loadPersistedState

  // Initial load and connect - STATELESS BEHAVIOR
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
      fetchStatusInProgressRef.current = false
      setConnected(false)
      setReconnecting(false)
      setSyncStatus(null)
      return
    }
    
    // STATELESS: On refresh/load - fetch status from backend first (ONCE on syncId change)
    // Only fetch if not already in progress to prevent infinite loops
    // Use refs to ensure we always have the latest functions (avoids TDZ)
    if (!fetchStatusInProgressRef.current && fetchSyncStatusRef.current) {
      fetchSyncStatusRef.current()
    }
    
    // Load persisted state from localStorage (for immediate UI display)
    if (loadPersistedStateRef.current) {
      loadPersistedStateRef.current()
    }
    
    // Small delay before connecting to avoid rapid reconnection loops
    const connectTimeout = setTimeout(() => {
      if (connectRef.current) {
        connectRef.current()
      }
    }, 100)
    
    // Cleanup on unmount
    return () => {
      clearTimeout(connectTimeout)
      if (batchTimeoutRef.current) {
        clearTimeout(batchTimeoutRef.current)
        batchTimeoutRef.current = null
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      fetchStatusInProgressRef.current = false
      eventBatchRef.current = []
      setConnected(false)
      setReconnecting(false)
      eventRef.current = null  // Clear event ref on cleanup
    }
    // Only depend on syncId - refs are updated synchronously above, so they're always current
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncId])
  
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
    syncStatus,  // Backend sync status (fetched on refresh)
    reconnect
  }
}
