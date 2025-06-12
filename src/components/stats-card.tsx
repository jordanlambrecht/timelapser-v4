import { Card, CardContent } from "@/components/ui/card"
import { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface StatsCardProps {
  title: string
  value: string | number
  description?: string
  icon: LucideIcon
  trend?: {
    value: number
    label: string
  }
  className?: string
  color?: 'pink' | 'cyan' | 'purple' | 'success' | 'yellow'
}

export function StatsCard({ 
  title, 
  value, 
  description, 
  icon: Icon, 
  trend, 
  className,
  color = 'pink'
}: StatsCardProps) {
  const colorVariants = {
    pink: {
      bg: 'from-pink/20 to-pink/5',
      border: 'border-pink/30',
      icon: 'bg-pink/20 border-pink/30 text-pink',
      glow: 'hover:shadow-pink/20'
    },
    cyan: {
      bg: 'from-cyan/20 to-cyan/5', 
      border: 'border-cyan/30',
      icon: 'bg-cyan/20 border-cyan/30 text-cyan',
      glow: 'hover:shadow-cyan/20'
    },
    purple: {
      bg: 'from-purple/20 to-purple/5',
      border: 'border-purple/30', 
      icon: 'bg-purple/20 border-purple/30 text-purple-light',
      glow: 'hover:shadow-purple/20'
    },
    success: {
      bg: 'from-success/20 to-success/5',
      border: 'border-success/30',
      icon: 'bg-success/20 border-success/30 text-success', 
      glow: 'hover:shadow-success/20'
    },
    yellow: {
      bg: 'from-yellow/20 to-yellow/5',
      border: 'border-yellow/30',
      icon: 'bg-yellow/20 border-yellow/30 text-yellow',
      glow: 'hover:shadow-yellow/20'
    }
  }

  const variant = colorVariants[color]

  return (
    <Card className={cn(
      "glass hover-lift relative overflow-hidden group transition-all duration-500",
      `bg-gradient-to-br ${variant.bg}`,
      `border ${variant.border}`,
      `hover:shadow-2xl ${variant.glow}`,
      className
    )}>
      {/* Animated background accent */}
      <div className={cn(
        "absolute -top-2 -right-2 w-20 h-20 rounded-full opacity-20 group-hover:opacity-30 transition-opacity duration-500",
        `bg-gradient-to-bl ${variant.bg}`
      )} />
      
      <CardContent className="p-6 relative">
        <div className="flex items-start justify-between">
          <div className="space-y-2 flex-1">
            <p className="text-grey-light/70 text-sm font-medium uppercase tracking-wide">
              {title}
            </p>
            <p className="text-4xl font-bold text-white group-hover:scale-105 transition-transform duration-300">
              {value}
            </p>
            {description && (
              <p className="text-grey-light/60 text-sm">
                {description}
              </p>
            )}
            {trend && (
              <div className="flex items-center space-x-2 text-sm">
                <span className={cn(
                  "font-medium px-2 py-1 rounded-full",
                  trend.value > 0 ? "text-success bg-success/20" : 
                  trend.value < 0 ? "text-failure bg-failure/20" : "text-grey-light/60 bg-grey-light/10"
                )}>
                  {trend.value > 0 ? "↗" : trend.value < 0 ? "↘" : "→"} {Math.abs(trend.value)}%
                </span>
                <span className="text-grey-light/60 text-xs">{trend.label}</span>
              </div>
            )}
          </div>
          
          <div className="flex-shrink-0 ml-4">
            <div className={cn(
              "w-14 h-14 rounded-2xl border flex items-center justify-center group-hover:scale-110 transition-all duration-300",
              variant.icon
            )}>
              <Icon className="w-7 h-7" />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
