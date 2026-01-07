"use client"

import { useState, useEffect, useCallback } from "react"
import { Sidebar } from "@/components/sidebar"
import { ChatHeader } from "@/components/chat-header"
import { ChatArea } from "@/components/chat-area"
import { ChatInput } from "@/components/chat-input"
import { PromptModal } from "@/components/prompt-modal"
import { useSession } from "@/hooks/use-session"
import { useAuth } from "@/components/auth/auth-provider"
import { chatApi, promptsApi, healthApi, sessionApi } from "@/lib/api"
import type { Message, ChatSession, SystemPrompt, HealthStatus } from "@/lib/types"

export default function Home() {
  const { session: authSession } = useAuth()
  const { sessionId, isLoading: sessionLoading, createNewSession } = useSession()

  // State
  const [messages, setMessages] = useState<Message[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [promptModalOpen, setPromptModalOpen] = useState(false)
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [currentModel, setCurrentModel] = useState<string>("loading...")
  const [healthStatus, setHealthStatus] = useState<HealthStatus>({
    api: "down",
    mcp: "down",
    ai: "down",
  })

  // Load user's sessions and prompts when authenticated
  useEffect(() => {
    const userId = authSession?.user?.id
    if (!userId) return

    const loadUserData = async () => {
      try {
        // Load user's sessions
        const sessionsResponse = await sessionApi.listByUser(userId)
        const loadedSessions: ChatSession[] = sessionsResponse.sessions.map((s) => ({
          id: s.session_id,
          title: s.title || "New Chat",
          createdAt: new Date(s.created_at),
          lastMessageAt: new Date(s.last_activity),
        }))
        setSessions(loadedSessions)

        // If we have sessions, set the most recent one as active
        if (loadedSessions.length > 0 && !activeSessionId) {
          setActiveSessionId(loadedSessions[0].id)
        }
      } catch (error) {
        console.error("Failed to load sessions:", error)
      }

      try {
        // Load prompts (system defaults + user's custom prompts)
        const promptsResponse = await promptsApi.list(userId)
        setPrompts(
          promptsResponse.prompts.map((p) => ({
            id: p.id,
            name: p.name,
            content: p.prompt,
            isActive: p.is_active,
            createdAt: new Date(p.created_at),
            updatedAt: new Date(p.updated_at),
            userId: p.user_id,
          }))
        )
      } catch (error) {
        console.error("Failed to load prompts:", error)
      }
    }

    loadUserData()
  }, [authSession?.user?.id])

  // Check health status on mount and periodically
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const status = await healthApi.getStatus()
        setHealthStatus(status)

        // Also get AI model info
        const aiHealth = await healthApi.checkAi()
        setCurrentModel(aiHealth.primary_model)
      } catch (error) {
        console.error("Failed to check health:", error)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30 seconds

    return () => clearInterval(interval)
  }, [])

  // Set active session when session hook provides a session
  // This handles the case where user has no existing sessions
  useEffect(() => {
    if (sessionId && !activeSessionId && sessions.length === 0) {
      setActiveSessionId(sessionId)
      // Add initial session to list if not exists
      setSessions((prev) => {
        if (prev.some((s) => s.id === sessionId)) return prev
        return [
          {
            id: sessionId,
            title: "New Chat",
            createdAt: new Date(),
            lastMessageAt: new Date(),
          },
          ...prev,
        ]
      })
    }
  }, [sessionId, activeSessionId, sessions.length])

  // Handlers
  const handleNewChat = useCallback(async () => {
    try {
      // Pass authenticated user ID to associate session with user
      const userId = authSession?.user?.id
      const newSessionId = await createNewSession(userId)
      const newSession: ChatSession = {
        id: newSessionId,
        title: "New Chat",
        createdAt: new Date(),
        lastMessageAt: new Date(),
      }
      setSessions((prev) => [newSession, ...prev])
      setActiveSessionId(newSessionId)
      setMessages([])
    } catch (error) {
      console.error("Failed to create new chat:", error)
    }
  }, [createNewSession, authSession])

  const handleSelectSession = useCallback((id: string) => {
    setActiveSessionId(id)
    // In a full implementation, load messages for this session from storage/backend
    setMessages([])
  }, [])

  const handleDeleteSession = useCallback(
    (id: string) => {
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (activeSessionId === id) {
        setActiveSessionId(null)
        setMessages([])
      }
    },
    [activeSessionId]
  )

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!activeSessionId) {
        console.error("No active session")
        return
      }

      // Add user message
      const userMessage: Message = {
        id: Date.now().toString(),
        role: "user",
        content,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMessage])

      // Update session title if it's the first message
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === activeSessionId && s.title === "New Chat") {
            return {
              ...s,
              title: content.slice(0, 30) + (content.length > 30 ? "..." : ""),
              lastMessageAt: new Date(),
            }
          }
          return s
        })
      )

      setIsStreaming(true)

      try {
        // Use streaming API
        let fullResponse = ""

        const abort = chatApi.stream(activeSessionId, content, {
          onProcessing: () => {
            // Could show a "thinking" indicator
          },
          onChunk: (chunk, accumulated) => {
            fullResponse = accumulated
            // Update the assistant message as chunks come in
            setMessages((prev) => {
              const lastMsg = prev[prev.length - 1]
              if (lastMsg?.role === "assistant" && lastMsg.id === "streaming") {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMsg, content: accumulated },
                ]
              }
              // Add new streaming message
              return [
                ...prev,
                {
                  id: "streaming",
                  role: "assistant",
                  content: accumulated,
                  timestamp: new Date(),
                  model: currentModel,
                },
              ]
            })
          },
          onComplete: (response) => {
            // Replace streaming message with final message
            setMessages((prev) => {
              const filtered = prev.filter((m) => m.id !== "streaming")
              return [
                ...filtered,
                {
                  id: (Date.now() + 1).toString(),
                  role: "assistant",
                  content: response.answer,
                  timestamp: new Date(),
                  model: response.model_used || currentModel,
                },
              ]
            })
          },
          onError: (error) => {
            console.error("Chat error:", error)
            setMessages((prev) => {
              const filtered = prev.filter((m) => m.id !== "streaming")
              return [
                ...filtered,
                {
                  id: (Date.now() + 1).toString(),
                  role: "assistant",
                  content: `Sorry, an error occurred: ${error}`,
                  timestamp: new Date(),
                },
              ]
            })
          },
          onDone: () => {
            setIsStreaming(false)
          },
        })

        // Store abort function if needed for cancellation
      } catch (error) {
        console.error("Failed to send message:", error)
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: "assistant",
            content: "Sorry, I couldn't process your request. Please try again.",
            timestamp: new Date(),
          },
        ])
        setIsStreaming(false)
      }
    },
    [activeSessionId, currentModel]
  )

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      handleSendMessage(suggestion)
    },
    [handleSendMessage]
  )

  // Prompt management handlers
  const handleActivatePrompt = useCallback(async (id: string) => {
    try {
      await promptsApi.activate(id)
      setPrompts((prev) => prev.map((p) => ({ ...p, isActive: p.id === id })))
    } catch (error) {
      console.error("Failed to activate prompt:", error)
    }
  }, [])

  const handleDeactivatePrompt = useCallback(() => {
    // Note: Backend doesn't have a deactivate endpoint,
    // but we can update local state for UI purposes
    setPrompts((prev) => prev.map((p) => ({ ...p, isActive: false })))
  }, [])

  const handleDeletePrompt = useCallback(async (id: string) => {
    try {
      await promptsApi.delete(id)
      setPrompts((prev) => prev.filter((p) => p.id !== id))
    } catch (error) {
      console.error("Failed to delete prompt:", error)
    }
  }, [])

  const handleCreatePrompt = useCallback(async (name: string, content: string) => {
    try {
      const userId = authSession?.user?.id
      const response = await promptsApi.create({ 
        name, 
        prompt: content,
        user_id: userId  // Associate prompt with current user
      })
      const newPrompt: SystemPrompt = {
        id: response.id,
        name: response.name,
        content: response.prompt,
        isActive: response.is_active,
        createdAt: new Date(response.created_at),
        updatedAt: new Date(response.updated_at),
      }
      setPrompts((prev) => [...prev, newPrompt])
    } catch (error) {
      console.error("Failed to create prompt:", error)
    }
  }, [authSession?.user?.id])

  const handleUpdatePrompt = useCallback(async (id: string, name: string, content: string) => {
    try {
      await promptsApi.update(id, { name, prompt: content })
      setPrompts((prev) =>
        prev.map((p) =>
          p.id === id
            ? { ...p, name, content, updatedAt: new Date() }
            : p
        )
      )
    } catch (error) {
      console.error("Failed to update prompt:", error)
    }
  }, [])

  const hasActivePrompt = prompts.some((p) => p.isActive)

  // Show loading state while session initializes
  if (sessionLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-muted-foreground">Initializing...</div>
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <ChatHeader healthStatus={healthStatus} currentModel={currentModel} />
        <ChatArea messages={messages} isStreaming={isStreaming} onSuggestionClick={handleSuggestionClick} />
        <ChatInput
          onSendMessage={handleSendMessage}
          onOpenPromptSettings={() => setPromptModalOpen(true)}
          isStreaming={isStreaming}
          hasActivePrompt={hasActivePrompt}
        />
      </div>

      {/* Prompt Settings Modal */}
      <PromptModal
        open={promptModalOpen}
        onOpenChange={setPromptModalOpen}
        prompts={prompts}
        onActivatePrompt={handleActivatePrompt}
        onDeactivatePrompt={handleDeactivatePrompt}
        onDeletePrompt={handleDeletePrompt}
        onCreatePrompt={handleCreatePrompt}
        onUpdatePrompt={handleUpdatePrompt}
      />
    </div>
  )
}
