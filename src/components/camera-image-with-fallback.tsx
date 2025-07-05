import { useState, useEffect, memo } from "react"
import Image from "next/image"
import { cn } from "@/lib/utils"

interface CameraImageWithFallbackProps {
  cameraId: number
  cameraName: string
  imageKey: number
  className?: string
  onLoad?: () => void
  onError?: () => void
}

const IMAGE_ENDPOINTS = [
  {
    name: "thumbnail",
    path: "latest-image/thumbnail",
    description: "200×150 thumbnail",
  },
  { name: "small", path: "latest-image/small", description: "800×600 small" },
  { name: "full", path: "latest-image/full", description: "Full resolution" },
] as const

// ✅ PERFORMANCE OPTIMIZATION: Memoized component with smart re-render logic
export const CameraImageWithFallback = memo(
  function CameraImageWithFallback({
    cameraId,
    cameraName,
    imageKey,
    className,
    onLoad,
    onError,
  }: CameraImageWithFallbackProps) {
    const [currentEndpointIndex, setCurrentEndpointIndex] = useState(0)
    const [isLoading, setIsLoading] = useState(true)
    const [hasError, setHasError] = useState(false)
    const [loadAttempts, setLoadAttempts] = useState(0)

    // Reset when imageKey changes (new image available)
    useEffect(() => {
      setCurrentEndpointIndex(0)
      setIsLoading(true)
      setHasError(false)
      setLoadAttempts(0)
    }, [imageKey])

    const currentEndpoint = IMAGE_ENDPOINTS[currentEndpointIndex]
    const imageUrl = `/api/cameras/${cameraId}/${currentEndpoint.path}?t=${imageKey}`

    const handleImageLoad = () => {
      setIsLoading(false)
      setHasError(false)
      if (onLoad) onLoad()
    }

    const handleImageError = () => {
      const newAttemptCount = loadAttempts + 1
      setLoadAttempts(newAttemptCount)

      // Try the next endpoint if available
      if (currentEndpointIndex < IMAGE_ENDPOINTS.length - 1) {
        setCurrentEndpointIndex(currentEndpointIndex + 1)
        setIsLoading(true)
      } else {
        // All endpoints failed
        setIsLoading(false)
        setHasError(true)
        if (onError) onError()
      }
    }

    // Show placeholder if all endpoints failed or no last image
    if (hasError) {
      return (
        <Image
          src='/assets/placeholder-camera.jpg'
          alt={`${cameraName} placeholder`}
          fill
          className={cn("object-cover opacity-60", className)}
          priority
        />
      )
    }

    return (
      <div className='relative w-full h-full'>
        {/* Loading state */}
        {isLoading && (
          <div className='absolute inset-0 flex items-center justify-center bg-gray-900/70 backdrop-blur-sm z-10'>
            <div className='flex flex-col items-center space-y-3'>
              <div className='w-8 h-8 border-2 rounded-full border-cyan/30 border-t-cyan animate-spin' />
              <div className='text-center'>
                <p className='text-xs font-medium text-gray-400'>
                  Loading {currentEndpoint.description}...
                </p>
                {loadAttempts > 0 && (
                  <p className='text-xs text-gray-500 mt-1'>
                    Attempt {loadAttempts + 1}/{IMAGE_ENDPOINTS.length}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Image */}
        <img
          src={imageUrl}
          alt={`Last capture from ${cameraName}`}
          className={cn(
            "absolute inset-0 w-full h-full object-cover transition-all duration-500",
            isLoading ? "opacity-0 scale-105" : "opacity-100 scale-100",
            className
          )}
          onLoad={handleImageLoad}
          onError={handleImageError}
        />

        {/* Debug info in development */}
        {process.env.NODE_ENV === "development" && !isLoading && !hasError && (
          <div className='absolute top-2 left-2 px-2 py-1 text-xs bg-black/70 text-green-400 rounded'>
            {currentEndpoint.name}
          </div>
        )}
      </div>
    )
  },
  // ✅ PERFORMANCE OPTIMIZATION: Only re-render when imageKey or cameraId changes
  (prevProps, nextProps) => {
    return (
      prevProps.cameraId === nextProps.cameraId &&
      prevProps.imageKey === nextProps.imageKey &&
      prevProps.cameraName === nextProps.cameraName
    )
  }
)
