// src/components/navigation-links.tsx
"use client"

import { usePathname } from "next/navigation"
import { LayoutDashboard, Settings, FileText, Video, Layers, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import { useState } from "react"

export function NavigationLinks() {
  const pathname = usePathname()
  const [showSettingsMenu, setShowSettingsMenu] = useState(false)

  const links = [
    {
      href: "/",
      label: "Dashboard",
      icon: LayoutDashboard,
      isActive: pathname === "/",
    },
    {
      href: "/timelapses",
      label: "Timelapses",
      icon: Video,
      isActive: pathname.startsWith("/timelapses"),
    },
    {
      href: "/logs",
      label: "Logs",
      icon: FileText,
      isActive: pathname === "/logs",
    },
  ]

  const settingsLinks = [
    {
      href: "/settings",
      label: "Settings",
      icon: Settings,
    },
    {
      href: "/overlays",
      label: "Overlays",
      icon: Layers,
    },
  ]

  const isSettingsActive = pathname === "/settings" || pathname === "/overlays"

  return (
    <div className='hidden md:flex items-center space-x-1 bg-black/30 rounded-full p-1 border border-purple-muted/30 backdrop-blur-sm'>
      {links.map((link) => {
        const Icon = link.icon
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "flex items-center space-x-2 px-6 py-2 rounded-full transition-all duration-300 font-medium",
              link.isActive
                ? "bg-gradient-to-r from-pink/80 to-cyan/80 text-black shadow-lg"
                : "text-white hover:text-pink hover:bg-black/30"
            )}
          >
            <Icon className='w-4 h-4' />
            <span>{link.label}</span>
          </Link>
        )
      })}
      
      {/* Settings with Dropdown */}
      <div 
        className="relative"
        onMouseEnter={() => setShowSettingsMenu(true)}
        onMouseLeave={() => setShowSettingsMenu(false)}
      >
        <div
          className={cn(
            "flex items-center space-x-2 px-6 py-2 rounded-full transition-all duration-300 font-medium cursor-pointer",
            isSettingsActive
              ? "bg-gradient-to-r from-pink/80 to-cyan/80 text-black shadow-lg"
              : "text-white hover:text-pink hover:bg-black/30"
          )}
        >
          <Settings className='w-4 h-4' />
          <span>Settings</span>
          <ChevronDown className={cn(
            'w-3 h-3 transition-transform duration-200',
            showSettingsMenu ? 'rotate-180' : ''
          )} />
        </div>
        
        {/* Dropdown Menu */}
        {showSettingsMenu && (
          <div className="absolute top-full left-0 mt-2 w-48 bg-black/90 backdrop-blur-sm border border-purple-muted/30 rounded-lg shadow-lg z-50">
            {settingsLinks.map((link) => {
              const Icon = link.icon
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "flex items-center space-x-3 px-4 py-3 transition-all duration-200 font-medium first:rounded-t-lg last:rounded-b-lg",
                    pathname === link.href
                      ? "bg-gradient-to-r from-pink/20 to-cyan/20 text-pink"
                      : "text-white hover:text-pink hover:bg-black/40"
                  )}
                >
                  <Icon className='w-4 h-4' />
                  <span>{link.label}</span>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
