"use client"

import React, { createContext, useContext, useEffect, useRef, useState } from "react"

interface SSEEvent {
  type: string
  data?: any
  timestamp: string
  [key: string]: any
}

interface SSEContextType {
  isConnected: boolean
  connectionAttempts: number
  lastEvent: SSEEvent | null
  subscribe: (callback: (event: SSEEvent) => void) => () => void
}

const SSEContext = createContext<SSEContextType | null>(null)

export function SSEProvider({ children }: { children: React.ReactNode }) {
  const [isConnected, setIsConnected] = useState(false)
  const [connectionAttempts, setConnectionAttempts] = useState(0)
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null)
  
  const eventSourceRef = useRef<EventSource | null>(null)
  const subscribersRef = useRef<Set<(event: SSEEvent) => void>>(new Set())
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(true)

  const cleanup = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    setIsConnected(false)
  }

  const connect = () => {
    if (!mountedRef.current) return
    
    cleanup()

    try {
      console.log("🔗 Creating centralized SSE connection")
      const eventSource = new EventSource("/api/events")
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        if (!mountedRef.current) return
        console.log("✅ SSE connected successfully")
        setIsConnected(true)
        setConnectionAttempts(0) // Reset on successful connection
      }

      eventSource.onmessage = (event) => {
        if (!mountedRef.current) return
        
        try {
          const data = JSON.parse(event.data)
          setLastEvent(data)
          
          // Notify all subscribers
          subscribersRef.current.forEach(callback => {
            try {
              callback(data)
            } catch (error) {
              console.error("❌ SSE subscriber error:", error)
            }
          })
        } catch (error) {
          console.error("❌ Failed to parse SSE event:", error)
        }
      }

      eventSource.onerror = () => {
        if (!mountedRef.current) return
        
        console.log("🔌 SSE connection lost, attempting reconnect...")
        setIsConnected(false)
        
        setConnectionAttempts(prev => {
          const attempts = prev + 1
          const maxAttempts = 10
          
          if (attempts <= maxAttempts) {
            // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
            const delay = Math.min(1000 * Math.pow(2, attempts - 1), 30000)
            
            reconnectTimerRef.current = setTimeout(() => {
              if (mountedRef.current) {
                console.log(`🔄 SSE reconnect attempt ${attempts}/${maxAttempts} in ${delay}ms`)
                connect()
              }
            }, delay)
          } else {
            console.error("❌ SSE max reconnection attempts reached")
          }
          
          return attempts
        })
      }

    } catch (error) {
      console.error("❌ Failed to create SSE connection:", error)
      setIsConnected(false)
    }
  }

  const subscribe = (callback: (event: SSEEvent) => void) => {
    subscribersRef.current.add(callback)
    
    // Return unsubscribe function
    return () => {
      subscribersRef.current.delete(callback)
    }
  }

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      cleanup()
    }
  }, [])

  const contextValue: SSEContextType = {
    isConnected,
    connectionAttempts,
    lastEvent,
    subscribe,
  }

  return (
    <SSEContext.Provider value={contextValue}>
      {children}
    </SSEContext.Provider>
  )
}

export function useSSE() {
  const context = useContext(SSEContext)
  if (!context) {
    throw new Error("useSSE must be used within an SSEProvider")
  }
  return context
}

// Specialized hook for subscribing to specific events
export function useSSESubscription<T = any>(
  eventFilter: (event: SSEEvent) => boolean,
  callback: (event: SSEEvent & { data: T }) => void,
  dependencies: any[] = []
) {
  const { subscribe } = useSSE()

  useEffect(() => {
    const unsubscribe = subscribe((event) => {
      if (eventFilter(event)) {
        callback(event as SSEEvent & { data: T })
      }
    })

    return unsubscribe
  }, [subscribe, ...dependencies])
}
