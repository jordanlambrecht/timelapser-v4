// src/components/ui/video-player.tsx
"use client"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  RotateCcw,
  Download,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { VideoPlayerProps } from "@/types"

export function VideoPlayer({
  src,
  poster,
  title,
  className,
  showDownload = false,
  onDownload,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showControls, setShowControls] = useState(true)

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted
      setIsMuted(!isMuted)
    }
  }

  const toggleFullscreen = () => {
    if (videoRef.current) {
      if (!isFullscreen) {
        videoRef.current.requestFullscreen()
        setIsFullscreen(true)
      } else {
        document.exitFullscreen()
        setIsFullscreen(false)
      }
    }
  }

  const restart = () => {
    if (videoRef.current) {
      videoRef.current.currentTime = 0
      videoRef.current.play()
      setIsPlaying(true)
    }
  }

  return (
    <div
      className={cn(
        "relative group bg-black rounded-xl overflow-hidden border border-purple-muted/30",
        className
      )}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
    >
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        className='w-full h-full object-contain'
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Controls Overlay */}
      <div
        className={cn(
          "absolute inset-0 flex items-center justify-center transition-opacity duration-300",
          showControls || !isPlaying ? "opacity-100" : "opacity-0"
        )}
      >
        {/* Play/Pause Button (Center) */}
        {!isPlaying && (
          <Button
            onClick={togglePlay}
            size='lg'
            className='bg-white/10 hover:bg-white/20 backdrop-blur-sm border-none w-16 h-16 rounded-full'
          >
            <Play className='w-8 h-8 text-white ml-1' />
          </Button>
        )}
      </div>

      {/* Bottom Controls */}
      <div
        className={cn(
          "absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 via-black/20 to-transparent transition-opacity duration-300",
          showControls ? "opacity-100" : "opacity-0"
        )}
      >
        <div className='flex items-center justify-between'>
          <div className='flex items-center space-x-2'>
            <Button
              onClick={togglePlay}
              size='sm'
              variant='ghost'
              className='text-white hover:bg-white/20 h-8 w-8 p-0'
            >
              {isPlaying ? (
                <Pause className='w-4 h-4' />
              ) : (
                <Play className='w-4 h-4' />
              )}
            </Button>

            <Button
              onClick={restart}
              size='sm'
              variant='ghost'
              className='text-white hover:bg-white/20 h-8 w-8 p-0'
            >
              <RotateCcw className='w-4 h-4' />
            </Button>

            <Button
              onClick={toggleMute}
              size='sm'
              variant='ghost'
              className='text-white hover:bg-white/20 h-8 w-8 p-0'
            >
              {isMuted ? (
                <VolumeX className='w-4 h-4' />
              ) : (
                <Volume2 className='w-4 h-4' />
              )}
            </Button>

            {title && (
              <span className='text-sm font-medium text-white/80 ml-2 truncate'>
                {title}
              </span>
            )}
          </div>

          <div className='flex items-center space-x-2'>
            {showDownload && onDownload && (
              <Button
                onClick={onDownload}
                size='sm'
                variant='ghost'
                className='text-white hover:bg-white/20 h-8 w-8 p-0'
              >
                <Download className='w-4 h-4' />
              </Button>
            )}

            <Button
              onClick={toggleFullscreen}
              size='sm'
              variant='ghost'
              className='text-white hover:bg-white/20 h-8 w-8 p-0'
            >
              <Maximize className='w-4 h-4' />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
