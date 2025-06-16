// src/components/video-name-modal.tsx
import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Video, Sparkles } from "lucide-react"

interface VideoNameModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (videoName: string) => void
  cameraName: string
  defaultName: string
}

export function VideoNameModal({
  isOpen,
  onClose,
  onConfirm,
  cameraName,
  defaultName,
}: VideoNameModalProps) {
  const [videoName, setVideoName] = useState(defaultName)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (videoName.trim()) {
      onConfirm(videoName.trim())
    }
  }

  // Reset to default when modal opens
  useEffect(() => {
    if (isOpen) {
      setVideoName(defaultName)
    }
  }, [isOpen, defaultName])

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className='glass-strong border-purple-muted/50 max-w-md'>
        <DialogHeader className='relative'>
          <div className='absolute -top-2 -right-2 w-16 h-16 bg-gradient-to-bl from-cyan/10 to-transparent rounded-full' />
          <DialogTitle className='flex items-center space-x-3 text-xl'>
            <div className='p-2 bg-gradient-to-br from-cyan/20 to-purple/20 rounded-xl'>
              <Video className='w-6 h-6 text-white' />
            </div>
            <span className='text-white'>Generate Timelapse Video</span>
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className='space-y-6 mt-6'>
          <div className='space-y-4'>
            <div className='flex items-center space-x-2 text-sm text-grey-light/70'>
              <Sparkles className='w-4 h-4 text-cyan/70' />
              <span>
                Creating video from{" "}
                <strong className='text-white'>{cameraName}</strong> images
              </span>
            </div>

            <div className='space-y-3'>
              <Label htmlFor='video_name' className='text-white font-medium'>
                Video Name
              </Label>
              <Input
                id='video_name'
                value={videoName}
                onChange={(e) => setVideoName(e.target.value)}
                placeholder='Enter video name...'
                className='bg-black/30 border-purple-muted/30 text-white placeholder:text-grey-light/40 focus:border-cyan/50 focus:ring-2 focus:ring-cyan/20 rounded-xl h-12'
                autoFocus
                required
              />
              <p className='text-xs text-grey-light/60'>
                The final filename will be:{" "}
                <span className='font-mono text-cyan/80'>{videoName}.mp4</span>
              </p>
            </div>

            <div className='p-4 bg-purple/10 border border-purple/20 rounded-xl'>
              <h4 className='text-sm font-medium text-white mb-2'>
                Video Settings
              </h4>
              <div className='grid grid-cols-2 gap-3 text-xs text-grey-light/70'>
                <div>
                  <span className='text-cyan/70'>Framerate:</span> 30 FPS
                </div>
                <div>
                  <span className='text-cyan/70'>Quality:</span> Medium
                </div>
                <div>
                  <span className='text-cyan/70'>Format:</span> MP4 (H.264)
                </div>
                <div>
                  <span className='text-cyan/70'>Resolution:</span> 1920x1080
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className='gap-3 pt-4'>
            <Button
              type='button'
              variant='outline'
              onClick={onClose}
              className='border-purple-muted/40 hover:bg-purple-muted/20 text-grey-light hover:text-white px-6'
            >
              Cancel
            </Button>
            <Button
              type='submit'
              className='bg-gradient-to-r from-cyan to-purple hover:from-cyan-dark hover:to-purple-dark text-black font-bold px-8 hover:shadow-lg hover:shadow-cyan/20 transition-all duration-300'
            >
              <Video className='w-4 h-4 mr-2' />
              Generate Video
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
