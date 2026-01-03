"use client"

import { useState, useEffect, useCallback } from "react"
import { sessionApi } from "@/lib/api"

const SESSION_KEY = "chattwelve_session_id"

export function useSession() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Initialize session on mount
  useEffect(() => {
    const initSession = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Check for existing session in localStorage
        const storedSessionId = localStorage.getItem(SESSION_KEY)

        if (storedSessionId) {
          // Validate the session still exists
          try {
            await sessionApi.get(storedSessionId)
            setSessionId(storedSessionId)
            setIsLoading(false)
            return
          } catch {
            // Session expired or invalid, create new one
            localStorage.removeItem(SESSION_KEY)
          }
        }

        // Create new session
        const session = await sessionApi.create()
        localStorage.setItem(SESSION_KEY, session.session_id)
        setSessionId(session.session_id)
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setIsLoading(false)
      }
    }

    initSession()
  }, [])

  // Create a new session (for "New Chat" functionality)
  const createNewSession = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const session = await sessionApi.create()
      localStorage.setItem(SESSION_KEY, session.session_id)
      setSessionId(session.session_id)
      return session.session_id
    } catch (err) {
      setError((err as Error).message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Delete current session
  const deleteSession = useCallback(async () => {
    if (!sessionId) return

    try {
      await sessionApi.delete(sessionId)
      localStorage.removeItem(SESSION_KEY)
      setSessionId(null)
    } catch (err) {
      // Session might already be expired, just clear local state
      localStorage.removeItem(SESSION_KEY)
      setSessionId(null)
    }
  }, [sessionId])

  return {
    sessionId,
    isLoading,
    error,
    createNewSession,
    deleteSession,
  }
}
