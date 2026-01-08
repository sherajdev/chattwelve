"use client"

import { useState, useEffect, useCallback } from "react"
import { sessionApi, persistentChatApi, profileApi, ChatSessionResponse } from "@/lib/api"

const SESSION_KEY = "chattwelve_session_id"

interface UseSessionOptions {
  userId?: string | null
  userEmail?: string | null
  userName?: string | null
}

export function useSession(options: UseSessionOptions = {}) {
  const { userId, userEmail, userName } = options
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<ChatSessionResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load sessions for authenticated user
  const loadSessions = useCallback(async () => {
    if (!userId) return

    try {
      const response = await persistentChatApi.listSessions(userId)
      setSessions(response.sessions)
    } catch (err) {
      console.error("Failed to load sessions:", err)
    }
  }, [userId])

  // Ensure profile exists before creating sessions
  const ensureProfile = useCallback(async () => {
    if (!userId || !userEmail) return

    try {
      await profileApi.sync({
        user_id: userId,
        email: userEmail,
        display_name: userName || null,
        avatar_url: null,
      })
    } catch (err) {
      console.error("Failed to sync profile:", err)
      // Don't throw - we'll let session creation fail with a clearer error
    }
  }, [userId, userEmail, userName])

  // Initialize session on mount
  useEffect(() => {
    const initSession = async () => {
      setIsLoading(true)
      setError(null)

      try {
        if (userId && userEmail) {
          // Authenticated user - use PostgreSQL sessions

          // First, ensure profile exists (fallback for if server-side sync failed)
          await ensureProfile()

          await loadSessions()

          // Check for existing session in localStorage
          const storedSessionId = localStorage.getItem(SESSION_KEY)
          if (storedSessionId) {
            // Verify it's a valid session for this user
            try {
              await persistentChatApi.getMessages(userId, storedSessionId)
              setSessionId(storedSessionId)
              setIsLoading(false)
              return
            } catch {
              // Session invalid or doesn't belong to user
              localStorage.removeItem(SESSION_KEY)
            }
          }

          // No valid session - create new one
          const session = await persistentChatApi.createSession(userId)
          localStorage.setItem(SESSION_KEY, session.id)
          setSessionId(session.id)
          await loadSessions()
        } else if (userId && !userEmail) {
          // userId but no email - wait for auth to fully load
          return
        } else {
          // Guest user - use SQLite sessions (legacy)
          const storedSessionId = localStorage.getItem(SESSION_KEY)

          if (storedSessionId) {
            try {
              await sessionApi.get(storedSessionId)
              setSessionId(storedSessionId)
              setIsLoading(false)
              return
            } catch {
              localStorage.removeItem(SESSION_KEY)
            }
          }

          const session = await sessionApi.create()
          localStorage.setItem(SESSION_KEY, session.session_id)
          setSessionId(session.session_id)
        }
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setIsLoading(false)
      }
    }

    initSession()
  }, [userId, userEmail, loadSessions, ensureProfile])

  // Create a new session
  const createNewSession = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      if (userId && userEmail) {
        // Authenticated - PostgreSQL
        // Ensure profile exists first
        await ensureProfile()
        const session = await persistentChatApi.createSession(userId)
        localStorage.setItem(SESSION_KEY, session.id)
        setSessionId(session.id)
        await loadSessions()
        return session.id
      } else if (userId && !userEmail) {
        throw new Error("User email not available")
      } else {
        // Guest - SQLite
        const session = await sessionApi.create()
        localStorage.setItem(SESSION_KEY, session.session_id)
        setSessionId(session.session_id)
        return session.session_id
      }
    } catch (err) {
      setError((err as Error).message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [userId, userEmail, loadSessions, ensureProfile])

  // Switch to an existing session
  const switchSession = useCallback((newSessionId: string) => {
    localStorage.setItem(SESSION_KEY, newSessionId)
    setSessionId(newSessionId)
  }, [])

  // Delete a session
  const deleteSession = useCallback(async (targetSessionId?: string) => {
    const idToDelete = targetSessionId || sessionId
    if (!idToDelete) return

    try {
      if (userId) {
        await persistentChatApi.deleteSession(userId, idToDelete)
        await loadSessions()

        // If we deleted current session, clear it
        if (idToDelete === sessionId) {
          localStorage.removeItem(SESSION_KEY)
          setSessionId(null)
        }
      } else {
        await sessionApi.delete(idToDelete)
        localStorage.removeItem(SESSION_KEY)
        setSessionId(null)
      }
    } catch (err) {
      // Session might already be deleted
      if (idToDelete === sessionId) {
        localStorage.removeItem(SESSION_KEY)
        setSessionId(null)
      }
    }
  }, [sessionId, userId, loadSessions])

  return {
    sessionId,
    sessions,
    isLoading,
    error,
    createNewSession,
    switchSession,
    deleteSession,
    refreshSessions: loadSessions,
  }
}
