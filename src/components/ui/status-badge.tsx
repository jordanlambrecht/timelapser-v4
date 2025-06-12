import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"

interface StatusBadgeProps {
  status: "online" | "offline" | "unknown"
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const variants = {
    online: "status-online",
    offline: "status-offline", 
    unknown: "status-unknown"
  }

  const icons = {
    online: "●",
    offline: "●", 
    unknown: "●"
  }

  return (
    <div className={cn(
      "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5",
      variants[status],
      className
    )}>
      <span className="text-current">{icons[status]}</span>
      <span className="capitalize">{status}</span>
    </div>
  )
}
