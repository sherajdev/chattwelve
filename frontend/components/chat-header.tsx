import { Badge } from "@/components/ui/badge"
import type { HealthStatus } from "@/lib/types"

interface ChatHeaderProps {
  healthStatus: HealthStatus
  currentModel: string
}

export function ChatHeader({ healthStatus, currentModel }: ChatHeaderProps) {
  const getStatusColor = (status: HealthStatus[keyof HealthStatus]) => {
    switch (status) {
      case "healthy":
        return "bg-[var(--status-success)]"
      case "degraded":
        return "bg-[var(--status-warning)]"
      case "down":
        return "bg-[var(--status-error)]"
    }
  }

  return (
    <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3">
      {/* Health Indicators */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5" title={`Backend API: ${healthStatus.api}`}>
          <div className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.api)}`} />
          <span className="text-xs text-muted-foreground">API</span>
        </div>
        <div className="flex items-center gap-1.5" title={`TwelveData MCP Server: ${healthStatus.mcp}`}>
          <div className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.mcp)}`} />
          <span className="text-xs text-muted-foreground">MCP</span>
        </div>
        <div className="flex items-center gap-1.5" title={`OpenRouter AI Service: ${healthStatus.ai}`}>
          <div className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.ai)}`} />
          <span className="text-xs text-muted-foreground">AI</span>
        </div>
      </div>

      {/* Current Model */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Current model:</span>
        <Badge variant="secondary" className="text-xs">
          {currentModel}
        </Badge>
      </div>
    </div>
  )
}
