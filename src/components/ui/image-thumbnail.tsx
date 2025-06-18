// src/components/ui/image-thumbnail.tsx
"use client"

import { useState } from "react"
import Image from "next/image"
import { 
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { 
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Download, Trash2, ZoomIn, ImageIcon, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface ImageThumbnailProps {
  imageId: number
  src: string
  alt: string
  capturedAt: string
  fileName?: string
  fileSize?: number
  isSelected?: boolean
  onSelect?: (selected: boolean) => void
  onDelete?: () => void
  onDownload?: () => void
  className?: string
  showActions?: boolean
  lazy?: boolean
}

export function ImageThumbnail({
  imageId,
  src,
  alt,
  capturedAt,
  fileName,
  fileSize,
  isSelected = false,
  onSelect,
  onDelete,
  onDownload,
  className,
  showActions = true,
  lazy = true
}: ImageThumbnailProps) {
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [fullImageOpen, setFullImageOpen] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "Unknown size"
    const mb = bytes / (1024 * 1024)
    return `${mb.toFixed(1)} MB`
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const handleImageLoad = () => {
    setIsLoading(false)
    setHasError(false)
  }

  const handleImageError = () => {
    setIsLoading(false)
    setHasError(true)
  }

  const handleClick = (e: React.MouseEvent) => {
    if (e.shiftKey && onSelect) {
      // Shift+click for selection
      e.preventDefault()
      onSelect(!isSelected)
    } else {
      // Regular click opens full image
      setFullImageOpen(true)
    }
  }

  const ThumbnailContent = () => (
    <div 
      className={cn(
        "relative group cursor-pointer rounded-lg overflow-hidden transition-all duration-200",
        "border-2 hover:border-cyan/50",
        isSelected ? "border-cyan bg-cyan/10" : "border-transparent",
        className
      )}
      onClick={handleClick}
    >
      {/* Selection indicator */}
      {isSelected && (
        <div className="absolute top-2 left-2 z-10 w-5 h-5 bg-cyan rounded-full border-2 border-white flex items-center justify-center">
          <div className="w-2 h-2 bg-white rounded-full" />
        </div>
      )}

      {/* Image */}
      <div className="relative aspect-square bg-gray-900">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        )}
        
        {hasError ? (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-800">
            <ImageIcon className="w-8 h-8 text-gray-500" />
          </div>
        ) : (
          <Image
            src={src}
            alt={alt}
            fill
            className="object-cover"
            onLoad={handleImageLoad}
            onError={handleImageError}
            loading={lazy ? "lazy" : "eager"}
          />
        )}
      </div>

      {/* Hover overlay with actions */}
      {showActions && (
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center">
          <div className="flex items-center space-x-2">
            <Button
              size="sm"
              variant="ghost"
              className="text-white hover:bg-white/20 h-8 w-8 p-0"
              onClick={(e) => {
                e.stopPropagation()
                setFullImageOpen(true)
              }}
            >
              <ZoomIn className="w-4 h-4" />
            </Button>
            
            {onDownload && (
              <Button
                size="sm"
                variant="ghost"
                className="text-white hover:bg-white/20 h-8 w-8 p-0"
                onClick={(e) => {
                  e.stopPropagation()
                  onDownload()
                }}
              >
                <Download className="w-4 h-4" />
              </Button>
            )}
            
            {onDelete && (
              <Button
                size="sm"
                variant="ghost"
                className="text-red-400 hover:bg-red-500/20 h-8 w-8 p-0"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete()
                }}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )

  return (
    <>
      <TooltipProvider>
        <Tooltip open={showTooltip && !isSelected}>
          <TooltipTrigger asChild>
            <div
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
            >
              <ThumbnailContent />
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="glass-strong border-purple-muted/50 p-0 w-80">
            <div className="p-3 space-y-2">
              {/* Larger preview */}
              <div className="relative aspect-video bg-gray-900 rounded-lg overflow-hidden">
                {hasError ? (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <ImageIcon className="w-12 h-12 text-gray-500" />
                  </div>
                ) : (
                  <Image
                    src={src}
                    alt={alt}
                    fill
                    className="object-cover"
                  />
                )}
              </div>
              
              {/* Image details */}
              <div className="space-y-1 text-sm">
                <div className="font-medium text-white">
                  {fileName || `Image ${imageId}`}
                </div>
                <div className="text-gray-400">
                  {formatDate(capturedAt)}
                </div>
                <div className="text-gray-400">
                  {formatFileSize(fileSize)}
                </div>
              </div>
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      {/* Full Image Modal */}
      <Dialog open={fullImageOpen} onOpenChange={setFullImageOpen}>
        <DialogContent className="max-w-6xl glass-strong border-purple-muted/50">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <ImageIcon className="w-5 h-5 text-cyan" />
              <span>{fileName || `Image ${imageId}`}</span>
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4">
            {/* Full size image */}
            <div className="relative aspect-video bg-gray-900 rounded-lg overflow-hidden">
              {hasError ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <ImageIcon className="w-16 h-16 text-gray-500" />
                  <span className="text-gray-400 ml-2">Image failed to load</span>
                </div>
              ) : (
                <Image
                  src={src.replace('/thumbnails/', '/images/')} // Use full image path
                  alt={alt}
                  fill
                  className="object-contain"
                />
              )}
            </div>
            
            {/* Image info and actions */}
            <div className="flex items-center justify-between p-4 bg-black/20 rounded-lg">
              <div className="space-y-1 text-sm">
                <div className="text-white font-medium">
                  Captured: {formatDate(capturedAt)}
                </div>
                <div className="text-gray-400">
                  Size: {formatFileSize(fileSize)}
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                {onDownload && (
                  <Button
                    onClick={onDownload}
                    size="sm"
                    className="bg-cyan/20 hover:bg-cyan/30 text-cyan border-cyan/30"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                )}
                
                {onDelete && (
                  <Button
                    onClick={() => {
                      onDelete()
                      setFullImageOpen(false)
                    }}
                    size="sm"
                    variant="destructive"
                    className="bg-red-500/20 hover:bg-red-500/30 text-red-400 border-red-500/30"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete
                  </Button>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
