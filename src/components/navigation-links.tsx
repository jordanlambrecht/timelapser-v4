'use client'

import { usePathname } from 'next/navigation'
import { LayoutDashboard, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

export function NavigationLinks() {
  const pathname = usePathname()
  
  const links = [
    {
      href: '/',
      label: 'Dashboard',
      icon: LayoutDashboard,
      isActive: pathname === '/'
    },
    {
      href: '/settings',
      label: 'Settings', 
      icon: Settings,
      isActive: pathname === '/settings'
    }
  ]

  return (
    <div className="hidden md:flex items-center space-x-1 bg-black/30 rounded-full p-1 border border-purple-muted/30 backdrop-blur-sm">
      {links.map((link) => {
        const Icon = link.icon
        return (
          <a
            key={link.href}
            href={link.href}
            className={cn(
              "flex items-center space-x-2 px-6 py-2 rounded-full transition-all duration-300 font-medium",
              link.isActive
                ? "bg-gradient-to-r from-pink/80 to-cyan/80 text-black shadow-lg"
                : "text-white hover:text-pink hover:bg-black/30"
            )}
          >
            <Icon className="w-4 h-4" />
            <span>{link.label}</span>
          </a>
        )
      })}
    </div>
  )
}
