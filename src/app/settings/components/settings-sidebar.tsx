// src/app/settings/components/settings-sidebar.tsx
"use client"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Camera,
  Image,
  Globe,
  Cloud,
  FileText,
  Shield,
  AlertTriangle,
  Info,
  Settings2
} from "lucide-react"

interface SettingsSidebarProps {
  activeSection: string
  onSectionChange: (section: string) => void
}

const settingsSections = [
  {
    id: "capture",
    label: "Capture",
    icon: Camera,
    description: "Image capture configuration"
  },
  {
    id: "thumbnails",
    label: "Thumbnails",
    icon: Image,
    description: "Thumbnail generation & management"
  },
  {
    id: "timezone",
    label: "Timezone",
    icon: Globe,
    description: "Date & time configuration"
  },
  {
    id: "weather",
    label: "Weather",
    icon: Cloud,
    description: "Weather API integration"
  },
  {
    id: "logging",
    label: "Logging",
    icon: FileText,
    description: "System logging configuration"
  },
  {
    id: "corruption",
    label: "Corruption Detection",
    icon: Shield,
    description: "Image corruption monitoring"
  },
  {
    id: "system",
    label: "System Maintenance",
    icon: AlertTriangle,
    description: "Database & system operations"
  },
  {
    id: "info",
    label: "Configuration Info",
    icon: Info,
    description: "Current system configuration"
  }
]

export function SettingsSidebar({ activeSection, onSectionChange }: SettingsSidebarProps) {
  return (
    <div className="w-64 border-r border-border/40">
      <div className="p-4 space-y-1">
        {settingsSections.map((section) => {
          const Icon = section.icon
          const isActive = activeSection === section.id
          
          return (
            <button
              key={section.id}
              className={cn(
                "flex items-center gap-3 w-full px-3 py-2 text-sm rounded-md transition-colors text-left",
                isActive 
                  ? "bg-muted text-foreground font-medium" 
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
              onClick={() => onSectionChange(section.id)}
            >
              <Icon className={cn(
                "h-4 w-4 shrink-0",
                isActive && "text-foreground"
              )} />
              <span className="truncate">
                {section.label}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}