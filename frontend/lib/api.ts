/**
 * API client for ChatTwelve backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Types matching backend responses
export interface SessionResponse {
  session_id: string
  created_at: string
  expires_at: string
}

export interface ChatResponse {
  answer: string
  query_type?: string
  symbol?: string
  data?: Record<string, unknown>
  model_used?: string
  tools_used?: string[]
  sources?: string[]
  cached?: boolean
  error?: {
    code: string
    message: string
  }
}

export interface PromptResponse {
  id: string
  name: string
  prompt: string
  description?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PromptListResponse {
  prompts: PromptResponse[]
  count: number
}

export interface HealthResponse {
  status: string
  version?: string
  timestamp?: string
}

export interface MCPHealthResponse {
  status: string
  mcp_server_url: string
  connected: boolean
  message?: string
}

export interface AIHealthResponse {
  status: string
  available: boolean
  primary_model: string
  fallback_model: string
  message?: string
  last_error?: string
}

export interface HealthStatus {
  api: 'healthy' | 'degraded' | 'down'
  mcp: 'healthy' | 'degraded' | 'down'
  ai: 'healthy' | 'degraded' | 'down'
}

// API Error class
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// Helper function for API requests
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${endpoint}`

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }))
    throw new ApiError(
      error.detail?.message || error.detail || error.message || 'Request failed',
      response.status,
      error.detail?.error?.code || error.code
    )
  }

  return response.json()
}

// Session API
export const sessionApi = {
  create: async (metadata?: Record<string, unknown>): Promise<SessionResponse> => {
    return request<SessionResponse>('/api/session', {
      method: 'POST',
      body: JSON.stringify(metadata ? { metadata } : {}),
    })
  },

  get: async (sessionId: string): Promise<SessionResponse> => {
    return request<SessionResponse>(`/api/session/${sessionId}`)
  },

  delete: async (sessionId: string): Promise<{ message: string; session_id: string }> => {
    return request(`/api/session/${sessionId}`, {
      method: 'DELETE',
    })
  },
}

// Chat API
export const chatApi = {
  send: async (sessionId: string, query: string): Promise<ChatResponse> => {
    return request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, query }),
    })
  },

  // SSE streaming for chat
  stream: (
    sessionId: string,
    query: string,
    callbacks: {
      onProcessing?: () => void
      onChunk?: (content: string, accumulated: string, progress: number) => void
      onComplete?: (response: ChatResponse) => void
      onError?: (error: string) => void
      onDone?: () => void
    }
  ): (() => void) => {
    const controller = new AbortController()

    const startStream = async () => {
      try {
        const response = await fetch(`${API_URL}/api/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, query }),
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        if (!reader) throw new Error('No response body')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              const eventType = line.slice(7)
              continue
            }
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6))

              if (data.status === 'processing') {
                callbacks.onProcessing?.()
              } else if (data.type === 'chunk') {
                callbacks.onChunk?.(data.content, data.accumulated, data.progress)
              } else if (data.answer !== undefined) {
                callbacks.onComplete?.(data as ChatResponse)
              } else if (data.error) {
                callbacks.onError?.(data.error)
              } else if (data.status === 'done') {
                callbacks.onDone?.()
              }
            }
          }
        }
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          callbacks.onError?.((error as Error).message)
        }
      }
    }

    startStream()

    // Return abort function
    return () => controller.abort()
  },
}

// Prompts API
export const promptsApi = {
  list: async (): Promise<PromptListResponse> => {
    return request<PromptListResponse>('/api/prompts')
  },

  getActive: async (): Promise<PromptResponse> => {
    return request<PromptResponse>('/api/prompts/active')
  },

  get: async (promptId: string): Promise<PromptResponse> => {
    return request<PromptResponse>(`/api/prompts/${promptId}`)
  },

  create: async (data: {
    name: string
    prompt: string
    description?: string
    is_active?: boolean
  }): Promise<PromptResponse> => {
    return request<PromptResponse>('/api/prompts', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  update: async (
    promptId: string,
    data: {
      name?: string
      prompt?: string
      description?: string
      is_active?: boolean
    }
  ): Promise<PromptResponse> => {
    return request<PromptResponse>(`/api/prompts/${promptId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  delete: async (promptId: string): Promise<{ message: string; prompt_id: string }> => {
    return request(`/api/prompts/${promptId}`, {
      method: 'DELETE',
    })
  },

  activate: async (promptId: string): Promise<PromptResponse> => {
    return request<PromptResponse>(`/api/prompts/${promptId}/activate`, {
      method: 'POST',
    })
  },
}

// Health API
export const healthApi = {
  check: async (): Promise<HealthResponse> => {
    return request<HealthResponse>('/api/health')
  },

  checkMcp: async (): Promise<MCPHealthResponse> => {
    return request<MCPHealthResponse>('/api/mcp-health')
  },

  checkAi: async (): Promise<AIHealthResponse> => {
    return request<AIHealthResponse>('/api/ai-health')
  },

  // Get combined health status
  getStatus: async (): Promise<HealthStatus> => {
    const [apiHealth, mcpHealth, aiHealth] = await Promise.allSettled([
      healthApi.check(),
      healthApi.checkMcp(),
      healthApi.checkAi(),
    ])

    const mapStatus = (
      result: PromiseSettledResult<{ status: string }>,
      connectedField?: string
    ): 'healthy' | 'degraded' | 'down' => {
      if (result.status === 'rejected') return 'down'
      const status = result.value.status
      if (status === 'ok' || status === 'healthy' || status === 'connected') return 'healthy'
      if (status === 'degraded') return 'degraded'
      return 'down'
    }

    return {
      api: mapStatus(apiHealth),
      mcp: mcpHealth.status === 'fulfilled' && mcpHealth.value.connected ? 'healthy' : 'down',
      ai: mapStatus(aiHealth),
    }
  },
}
