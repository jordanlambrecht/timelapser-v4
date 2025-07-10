"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Save, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

interface StickySaveButtonProps {
  show: boolean
  onSave: () => Promise<void> | void
  saving?: boolean
  disabled?: boolean
  saveText?: string
  savingText?: string
}

export function StickySaveButton({
  show,
  onSave,
  saving = false,
  disabled = false,
  saveText = "Save All Settings",
  savingText = "Saving Settings...",
}: StickySaveButtonProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (show) {
      // Small delay to allow for smooth animation
      const timer = setTimeout(() => setIsVisible(true), 100)
      return () => clearTimeout(timer)
    } else {
      setIsVisible(false)
    }
  }, [show])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSave()
  }

  return (
    <div
      className={cn(
        "fixed bottom-0 left-0 right-0 z-50 transition-transform duration-300 ease-in-out",
        "bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60",
        "border-t border-border shadow-lg",
        isVisible && show ? "translate-y-0" : "translate-y-full"
      )}
    >
      <div className='max-w-4xl mx-auto p-4'>
        <div className='flex justify-center'>
          <Button
            onClick={handleSave}
            disabled={saving || disabled}
            size='lg'
            className={cn(
              "transition-all duration-300 ease-in-out",
              "min-w-[200px] font-medium",
              "bg-primary hover:bg-primary/80 text-primary-foreground",
              "shadow-md hover:shadow-lg",
              saving && "cursor-not-allowed opacity-75"
            )}
          >
            {saving ? (
              <>
                <RefreshCw className='w-4 h-4 mr-2 animate-spin' />
                {savingText}
              </>
            ) : (
              <>
                <Save className='w-4 h-4 mr-2' />
                {saveText}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
