import { useState } from "react"
import {
  Eye,
  Edit,
  Star,
  Download,
  Trash2,
  Share,
  Link,
  Code,
  FolderOpen,
} from "lucide-react"
// Note: Using custom positioning instead of DropdownMenu for better control
import type { TimelapseForLibrary } from "@/hooks/use-timelapse-library"

interface ContextMenuProps {
  isOpen: boolean
  onClose: () => void
  timelapse: TimelapseForLibrary
  onAction: (action: string, timelapse: TimelapseForLibrary) => void
}

export function ContextMenu({
  isOpen,
  onClose,
  timelapse,
  onAction,
}: ContextMenuProps) {
  const handleAction = (action: string) => {
    onAction(action, timelapse)
    onClose()
  }

  if (!isOpen) return null

  const menuItems = [
    // Sharing section (future features)
    {
      group: "sharing",
      items: [
        {
          icon: Share,
          label: "Share...",
          action: "share",
          disabled: true,
          tooltip: "Coming soon",
        },
        {
          icon: Link,
          label: "Copy link",
          action: "copy_link",
          disabled: true,
          tooltip: "Coming soon",
        },
        {
          icon: Code,
          label: "Copy embed code",
          action: "copy_embed",
          disabled: true,
          tooltip: "Coming soon",
        },
      ],
    },
    // Current actions
    {
      group: "actions",
      items: [
        {
          icon: Eye,
          label: "View Details",
          action: "view_details",
          disabled: false,
        },
        {
          icon: Edit,
          label: "Rename",
          action: "rename",
          disabled: false,
        },
      ],
    },
    // Downloads and organization
    {
      group: "organization",
      items: [
        {
          icon: Download,
          label: "Download Images (ZIP)",
          action: "download_images",
          disabled: false,
        },
        {
          icon: FolderOpen,
          label: "Move to Folder",
          action: "move_folder",
          disabled: true,
          tooltip: "Coming soon",
        },
      ],
    },
    // Actions
    {
      group: "meta",
      items: [
        {
          icon: Star,
          label: timelapse.starred ? "Remove from Starred" : "Add to Starred",
          action: "toggle_star",
          disabled: false,
        },
        {
          icon: Trash2,
          label: "Delete",
          action: "delete",
          disabled: false,
          destructive: true,
        },
      ],
    },
  ]

  return (
    <div className='fixed inset-0 z-50' onClick={onClose}>
      <div
        className='absolute bg-white rounded-md shadow-lg border border-gray-200 py-2 min-w-[200px]'
        style={{
          // Position near where the user clicked
          // For now, we'll center it - in a real implementation,
          // you'd want to position it near the mouse/button
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {menuItems.map((group, groupIndex) => (
          <div key={group.group}>
            {group.items.map((item) => (
              <button
                key={item.action}
                onClick={() => handleAction(item.action)}
                disabled={item.disabled}
                className={`w-full px-4 py-2 text-left text-sm flex items-center space-x-3 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed ${
                  item.destructive
                    ? "text-red-600 hover:bg-red-50"
                    : "text-gray-700"
                }`}
                title={item.tooltip}
              >
                <item.icon className='h-4 w-4' />
                <span>{item.label}</span>
              </button>
            ))}
            {groupIndex < menuItems.length - 1 && (
              <hr className='my-1 border-gray-100' />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
