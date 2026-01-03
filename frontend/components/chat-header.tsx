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
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div
            className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.api)}`}
            title={`API: ${healthStatus.api}`}
          />
          <div
            className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.mcp)}`}
            title={`MCP: ${healthStatus.mcp}`}
          />
          <div className={`h-2 w-2 rounded-full ${getStatusColor(healthStatus.ai)}`} title={`AI: ${healthStatus.ai}`} />
        </div>
      </div>

      {/* Model Badge */}
      <Badge variant="secondary" className="text-xs">
        {currentModel}
      </Badge>
    </div>
  )
}
