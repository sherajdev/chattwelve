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
    <div
      className="flex items-center justify-between border-b border-border bg-card pl-14 pr-4 pb-3 md:px-4 md:py-3"
      style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))" }}
    >
      {/* Health Indicators */}
      <div className="flex items-center gap-2 md:gap-4">
        <div className="flex items-center gap-1" title={`Backend API: ${healthStatus.api}`}>
          <div className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.api)}`} />
          <span className="text-xs text-muted-foreground">API</span>
        </div>
        <div className="flex items-center gap-1" title={`TwelveData MCP Server: ${healthStatus.mcp}`}>
          <div className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.mcp)}`} />
          <span className="text-xs text-muted-foreground">MCP</span>
        </div>
        <div className="flex items-center gap-1" title={`OpenRouter AI Service: ${healthStatus.ai}`}>
          <div className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.ai)}`} />
          <span className="text-xs text-muted-foreground">AI</span>
        </div>
      </div>

      {/* Current Model */}
      <div className="flex items-center gap-1 md:gap-2">
        <span className="hidden text-xs text-muted-foreground sm:inline">Current model:</span>
        <Badge variant="secondary" className="text-xs max-w-[120px] md:max-w-none truncate">
          {currentModel}
        </Badge>
      </div>
    </div>
  )
}
