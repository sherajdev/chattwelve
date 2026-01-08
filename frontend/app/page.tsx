"use client"

import { useState, useEffect, useCallback } from "react"
import { Sidebar } from "@/components/sidebar"
import { ChatHeader } from "@/components/chat-header"
import { ChatArea } from "@/components/chat-area"
import { ChatInput } from "@/components/chat-input"
import { PromptModal } from "@/components/prompt-modal"
import { useSession } from "@/hooks/use-session"
import { useAuth } from "@/components/auth/auth-provider"
import { chatApi, promptsApi, healthApi, persistentChatApi } from "@/lib/api"
import type { Message, ChatSession, SystemPrompt, HealthStatus } from "@/lib/types"

export default function Home() {
  const { session: authSession } = useAuth()
  const userId = authSession?.user?.id
  const {
    sessionId,
    sessions: hookSessions,
    isLoading: sessionLoading,
    error: sessionError,
    createNewSession,
    switchSession,
    deleteSession,
    refreshSessions,
  } = useSession({ userId })

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

  // Sync sessions from hook to local state
  useEffect(() => {
    if (!userId) return

    // Map hook sessions to ChatSession format
    const mappedSessions: ChatSession[] = hookSessions.map((s) => ({
      id: s.id,
      title: s.title || "New Chat",
      createdAt: new Date(s.created_at),
      lastMessageAt: new Date(s.last_message_at),
    }))
    setSessions(mappedSessions)
    // Note: activeSessionId is set by the sessionId sync effect
  }, [hookSessions, userId])

  // Load prompts when authenticated
  useEffect(() => {
    if (!userId) return

    const loadPrompts = async () => {
      try {
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

    loadPrompts()
  }, [userId])

  // Load messages when active session changes (for authenticated users)
  useEffect(() => {
    if (!userId || !activeSessionId) return

    const loadMessages = async () => {
      try {
        const response = await persistentChatApi.getMessages(userId, activeSessionId)
        const loadedMessages: Message[] = response.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at),
          model: m.model,
        }))
        setMessages(loadedMessages)
      } catch (error) {
        console.error("Failed to load messages:", error)
        setMessages([])
      }
    }

    loadMessages()
  }, [userId, activeSessionId])

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

  // Sync sessionId from hook to activeSessionId
  // This ensures we have an active session when the hook provides one
  useEffect(() => {
    if (sessionId && !activeSessionId) {
      setActiveSessionId(sessionId)
    }
  }, [sessionId, activeSessionId])

  // Handlers
  const handleNewChat = useCallback(async () => {
    try {
      const newSessionId = await createNewSession()
      setActiveSessionId(newSessionId)
      setMessages([])
      // Sessions list will be refreshed by the hook
    } catch (error) {
      console.error("Failed to create new chat:", error)
    }
  }, [createNewSession])

  const handleSelectSession = useCallback((id: string) => {
    switchSession(id)
    setActiveSessionId(id)
    // Messages will be loaded by the activeSessionId effect
  }, [switchSession])

  const handleDeleteSession = useCallback(
    async (id: string) => {
      try {
        await deleteSession(id)
        if (activeSessionId === id) {
          setActiveSessionId(null)
          setMessages([])
        }
        // Sessions list will be refreshed by the hook
      } catch (error) {
        console.error("Failed to delete session:", error)
      }
    },
    [activeSessionId, deleteSession]
  )

  const handleSendMessage = useCallback(
    async (content: string) => {
      let currentSessionId = activeSessionId

      // Auto-create session if none exists
      if (!currentSessionId) {
        try {
          console.log("No active session, creating one...")
          currentSessionId = await createNewSession()
          setActiveSessionId(currentSessionId)
        } catch (error) {
          console.error("Failed to create session:", error)
          return
        }
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
          if (s.id === currentSessionId && s.title === "New Chat") {
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

        const abort = chatApi.stream(currentSessionId, content, {
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
        }, userId)

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
    [activeSessionId, currentModel, userId, createNewSession]
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
  }, [userId])

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

  // Show error state if session initialization failed
  if (sessionError) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background">
        <div className="text-destructive">Failed to initialize session: {sessionError}</div>
        <button
          onClick={() => window.location.reload()}
          className="rounded-md bg-primary px-4 py-2 text-primary-foreground"
        >
          Retry
        </button>
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
