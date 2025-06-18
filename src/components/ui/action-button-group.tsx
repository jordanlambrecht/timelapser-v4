// src/components/ui/action-button-group.tsx
"use client"

import { Button } from "@/components/ui/button"
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MoreVertical, LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface ActionItem {
  icon: LucideIcon
  label: string
  onClick: () => void
  variant?: "default" | "destructive" | "success" | "warning"
  disabled?: boolean
}

interface ActionButtonGroupProps {
  actions: ActionItem[]
  size?: "sm" | "lg"
  variant?: "buttons" | "dropdown" | "mixed"
  className?: string
  primaryActions?: number // Number of actions to show as buttons (rest in dropdown)
}

export function ActionButtonGroup({
  actions,
  size = "sm", 
  variant = "mixed",
  className,
  primaryActions = 2
}: ActionButtonGroupProps) {
  if (actions.length === 0) return null

  const getButtonVariant = (actionVariant?: string): "ghost" => {
    return "ghost" // Always use ghost variant for consistency
  }

  const getButtonClassName = (actionVariant?: string) => {
    const baseClasses = "h-8 w-8 p-0"
    
    switch (actionVariant) {
      case "destructive":
        return cn(baseClasses, "hover:bg-failure/20 text-failure/70 hover:text-failure")
      case "success":
        return cn(baseClasses, "hover:bg-success/20 text-success/70 hover:text-success")
      case "warning":
        return cn(baseClasses, "hover:bg-yellow/20 text-yellow/70 hover:text-yellow")
      default:
        return cn(baseClasses, "hover:bg-purple/20 text-purple-light/70 hover:text-purple-light")
    }
  }

  const getDropdownClassName = (actionVariant?: string) => {
    switch (actionVariant) {
      case "destructive":
        return "text-failure hover:bg-failure/20"
      case "success":  
        return "text-success hover:bg-success/20"
      case "warning":
        return "text-yellow hover:bg-yellow/20"
      default:
        return "text-white hover:bg-purple/20"
    }
  }

  if (variant === "buttons") {
    return (
      <div className={cn("flex items-center space-x-1", className)}>
        {actions.map((action, index) => {
          const Icon = action.icon
          return (
            <Button
              key={index}
              onClick={action.onClick}
              size={size}
              variant={getButtonVariant(action.variant)}
              disabled={action.disabled}
              className={getButtonClassName(action.variant)}
            >
              <Icon className="w-4 h-4" />
            </Button>
          )
        })}
      </div>
    )
  }

  if (variant === "dropdown") {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size={size}
            variant="ghost"
            className="h-8 w-8 p-0 hover:bg-purple/20 text-purple-light/70 hover:text-purple-light"
          >
            <MoreVertical className="w-4 h-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent 
          align="end" 
          className="glass-strong border-purple-muted/50"
        >
          {actions.map((action, index) => {
            const Icon = action.icon
            return (
              <DropdownMenuItem
                key={index}
                onClick={action.onClick}
                disabled={action.disabled}
                className={getDropdownClassName(action.variant)}
              >
                <Icon className="w-4 h-4 mr-2" />
                {action.label}
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  // Mixed variant: show primary actions as buttons, rest in dropdown
  const primaryActionsList = actions.slice(0, primaryActions)
  const secondaryActions = actions.slice(primaryActions)

  return (
    <div className={cn("flex items-center space-x-1", className)}>
      {/* Primary action buttons */}
      {primaryActionsList.map((action, index) => {
        const Icon = action.icon
        return (
          <Button
            key={index}
            onClick={action.onClick}
            size={size}
            variant={getButtonVariant(action.variant)}
            disabled={action.disabled}
            className={getButtonClassName(action.variant)}
          >
            <Icon className="w-4 h-4" />
          </Button>
        )
      })}

      {/* Secondary actions in dropdown */}
      {secondaryActions.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size={size}
              variant="ghost"
              className="h-8 w-8 p-0 hover:bg-purple/20 text-purple-light/70 hover:text-purple-light"
            >
              <MoreVertical className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent 
            align="end" 
            className="glass-strong border-purple-muted/50"
          >
            {secondaryActions.map((action, index) => {
              const Icon = action.icon
              return (
                <DropdownMenuItem
                  key={index}
                  onClick={action.onClick}
                  disabled={action.disabled}
                  className={getDropdownClassName(action.variant)}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {action.label}
                </DropdownMenuItem>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  )
}
