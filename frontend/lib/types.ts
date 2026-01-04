export interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  model?: string
}

export interface ChatSession {
  id: string
  title: string
  createdAt: Date
  lastMessageAt: Date
}

export interface SystemPrompt {
  id: string
  name: string
  content: string
  isActive: boolean
  createdAt: Date
  updatedAt: Date
}

export interface HealthStatus {
  api: "healthy" | "degraded" | "down"
  mcp: "healthy" | "degraded" | "down"
  ai: "healthy" | "degraded" | "down"
}
