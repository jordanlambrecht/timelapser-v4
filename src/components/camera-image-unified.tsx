/**
 *  Camera Image Component using Unified Latest-Image API
 *
 * EXAMPLE: How to migrate from old image serving to new unified system
 * This component demonstrates the recommended approach for displaying latest camera images
 */

import { useState, useEffect } from "react"
import Image from "next/image"
import { cn } from "@/lib/utils"
import { useLatestImageThumbnail } from "@/hooks/use-latest-image"
import { AlertTriangle, Eye, Shield } from "lucide-react"

interface CameraImageUnifiedProps {
  cameraId: number | string
  cameraName: string
  size?: "thumbnail" | "small" | "full"
  showMetadata?: boolean
  showCorruptionInfo?: boolean
  fallbackSrc?: string
  className?: string
  priority?: boolean
}

/**
 * Camera image component using the new unified latest-image API
 *
 * Features:
 * - Uses unified latest-image endpoints
 * - Built-in fallback handling
 * - Corruption score display
 * - Automatic refresh capability
 * - Optimized for different use cases (dashboard vs details)
 */
export function CameraImageUnified({
  cameraId,
  cameraName,
  size = "thumbnail",
  showMetadata = false,
  showCorruptionInfo = false,
  fallbackSrc = "/assets/placeholder-camera.jpg",
  className,
  priority = false,
}: CameraImageUnifiedProps) {
  const [hasError, setHasError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // Use the appropriate hook based on use case
  const {
    thumbnailUrl,
    hasImage,
    isLoading: dataLoading,
    error: dataError,
    imageData,
    refetch,
  } = useLatestImageThumbnail(cameraId)

  // Determine the actual image URL based on size
  const getImageUrl = () => {
    switch (size) {
      case "thumbnail":
        return `/api/cameras/${cameraId}/latest-image/thumbnail`
      case "small":
        return `/api/cameras/${cameraId}/latest-image/small`
      case "full":
        return `/api/cameras/${cameraId}/latest-image/full`
      default:
        return thumbnailUrl
    }
  }

  const imageUrl = hasImage && !hasError ? getImageUrl() : fallbackSrc
  const showFallback = !hasImage || hasError || dataError

  const handleImageLoad = () => {
    setIsLoading(false)
    setHasError(false)
  }

  const handleImageError = () => {
    setIsLoading(false)
    setHasError(true)
  }

  const handleRetry = () => {
    setHasError(false)
    setIsLoading(true)
    refetch()
  }

  return (
    <div className={cn("relative overflow-hidden", className)}>
      {/* Main Image */}
      <Image
        src={imageUrl}
        alt={
          showFallback
            ? `${cameraName} placeholder`
            : `Latest capture from ${cameraName}`
        }
        fill
        className={cn(
          "object-cover transition-opacity duration-300",
          isLoading ? "opacity-50" : "opacity-100",
          showFallback ? "opacity-60" : ""
        )}
        priority={priority}
        onLoad={handleImageLoad}
        onError={handleImageError}
        sizes={
          size === "thumbnail"
            ? "(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            : size === "small"
            ? "(max-width: 768px) 100vw, 50vw"
            : "100vw"
        }
      />

      {/* Loading indicator */}
      {(isLoading || dataLoading) && (
        <div className='absolute inset-0 flex items-center justify-center bg-black/50'>
          <div className='w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin' />
        </div>
      )}

      {/* Error state with retry */}
      {(hasError || dataError) && !isLoading && (
        <div className='absolute inset-0 flex flex-col items-center justify-center bg-black/70 text-white'>
          <AlertTriangle className='w-6 h-6 mb-2 text-yellow-400' />
          <p className='mb-2 text-xs text-center'>Failed to load image</p>
          <button
            onClick={handleRetry}
            className='px-3 py-1 text-xs bg-white/20 rounded hover:bg-white/30 transition-colors'
          >
            Retry
          </button>
        </div>
      )}

      {/* Image metadata overlay */}
      {showMetadata && imageData && !showFallback && (
        <div className='absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/80 via-black/40 to-transparent'>
          <div className='flex items-center justify-between text-xs text-white'>
            <div className='flex items-center space-x-2'>
              <Eye className='w-3 h-3' />
              <span>Day {imageData.dayNumber}</span>
            </div>
            <div className='flex items-center space-x-2'>
              <span>{new Date(imageData.capturedAt).toLocaleTimeString()}</span>
            </div>
          </div>
        </div>
      )}

      {/* Corruption score indicator */}
      {showCorruptionInfo && imageData && !showFallback && (
        <div className='absolute top-2 left-2'>
          <div
            className={cn(
              "flex items-center space-x-1 px-2 py-1 rounded-md backdrop-blur-sm",
              imageData.isFlagged
                ? "bg-red-500/20 border border-red-500/30"
                : imageData.corruptionScore >= 90
                ? "bg-green-500/20 border border-green-500/30"
                : imageData.corruptionScore >= 70
                ? "bg-blue-500/20 border border-blue-500/30"
                : "bg-yellow-500/20 border border-yellow-500/30"
            )}
          >
            <Shield className='w-3 h-3 text-white' />
            <span className='text-xs font-medium text-white'>
              {imageData.corruptionScore}
            </span>
          </div>
        </div>
      )}

      {/* No image indicator */}
      {!hasImage && !isLoading && !dataLoading && (
        <div className='absolute bottom-2 right-2'>
          <div className='px-2 py-1 text-xs text-white bg-black/60 rounded backdrop-blur-sm'>
            No captures yet
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Specialized component for dashboard camera cards
 * Pre-configured for optimal dashboard performance
 */
export function CameraCardImage({
  cameraId,
  cameraName,
  className,
  onRefetchReady,
}: {
  cameraId: number
  cameraName: string
  className?: string
  onRefetchReady?: (refetch: () => Promise<void>) => void
}) {
  const { refetch } = useLatestImageThumbnail(cameraId)

  // Expose refetch function to parent for SSE integration
  useEffect(() => {
    if (onRefetchReady) {
      onRefetchReady(refetch)
    }
  }, [onRefetchReady, refetch])

  return (
    <CameraImageUnified
      cameraId={cameraId}
      cameraName={cameraName}
      size='thumbnail'
      showMetadata={false}
      showCorruptionInfo={true}
      className={className}
      priority={true} // Dashboard images are high priority
    />
  )
}

/**
 * Specialized component for camera details page
 * Pre-configured for detailed viewing
 */
export function CameraDetailsImage({
  cameraId,
  cameraName,
  className,
}: {
  cameraId: number
  cameraName: string
  className?: string
}) {
  return (
    <CameraImageUnified
      cameraId={cameraId}
      cameraName={cameraName}
      size='small'
      showMetadata={true}
      showCorruptionInfo={true}
      className={className}
      priority={false}
    />
  )
}
