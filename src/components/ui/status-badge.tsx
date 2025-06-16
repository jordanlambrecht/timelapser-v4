// src/components/ui/status-badge.tsx
// Legacy component - prefer CombinedStatusBadge for new implementations
import { StatusBadge as ModernStatusBadge, ConnectionStatusBadge as ModernConnectionStatusBadge } from "./combined-status-badge"

// Re-export the modern components for backward compatibility
export const StatusBadge = ModernStatusBadge
export const ConnectionStatusBadge = ModernConnectionStatusBadge

// Legacy interface for compatibility
interface LegacyStatusBadgeProps {
  status: "online" | "offline" | "unknown"
  className?: string
}

// Legacy component kept for any direct imports
export function LegacyStatusBadge({ status, className }: LegacyStatusBadgeProps) {
  return <ModernStatusBadge status={status} className={className} />
}