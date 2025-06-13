import { useEffect, useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { Video, Loader2, Clock, Image as ImageIcon, Settings } from "lucide-react"

interface VideoProgressModalProps {
  isOpen: boolean
  cameraName: string
  videoName: string
  imageCount?: number
}

export function VideoProgressModal({ 
  isOpen, 
  cameraName, 
  videoName,
  imageCount = 0
}: VideoProgressModalProps) {
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState("Initializing...")
  const [elapsedTime, setElapsedTime] = useState(0)

  const steps = [
    { label: "Initializing video generation...", duration: 2 },
    { label: "Reading image files...", duration: 3 },
    { label: "Processing images...", duration: 5 },
    { label: "Encoding video with FFmpeg...", duration: 8 },
    { label: "Finalizing video file...", duration: 2 }
  ]

  useEffect(() => {
    if (!isOpen) {
      setProgress(0)
      setCurrentStep("Initializing...")
      setElapsedTime(0)
      return
    }

    let currentStepIndex = 0
    let stepProgress = 0
    let totalElapsed = 0

    const interval = setInterval(() => {
      totalElapsed += 0.5
      setElapsedTime(totalElapsed)

      const currentStepDuration = steps[currentStepIndex]?.duration || 1
      stepProgress += 0.5

      // Calculate overall progress
      const completedSteps = currentStepIndex
      const totalDuration = steps.reduce((sum, step) => sum + step.duration, 0)
      const progressInCurrentStep = Math.min(stepProgress / currentStepDuration, 1)
      const overallProgress = ((completedSteps + progressInCurrentStep) / steps.length) * 100

      setProgress(Math.min(overallProgress, 95)) // Cap at 95% until actual completion

      // Update current step
      if (currentStepIndex < steps.length) {
        setCurrentStep(steps[currentStepIndex].label)
      }

      // Move to next step
      if (stepProgress >= currentStepDuration && currentStepIndex < steps.length - 1) {
        currentStepIndex++
        stepProgress = 0
      }
    }, 500)

    return () => clearInterval(interval)
  }, [isOpen])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const estimatedDuration = steps.reduce((sum, step) => sum + step.duration, 0)

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent className="glass-strong border-purple-muted/50 max-w-lg pointer-events-auto" onPointerDownOutside={(e) => e.preventDefault()} onEscapeKeyDown={(e) => e.preventDefault()}>
        <DialogHeader className="relative">
          <div className="absolute -top-2 -right-2 w-16 h-16 bg-gradient-to-bl from-purple/10 to-transparent rounded-full" />
          <DialogTitle className="flex items-center space-x-3 text-xl">
            <div className="p-2 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-xl">
              <Video className="w-6 h-6 text-white" />
            </div>
            <span className="text-white">Generating Video...</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 mt-6">
          {/* Video Info */}
          <div className="p-4 bg-black/20 rounded-xl border border-purple-muted/20">
            <h3 className="font-medium text-white mb-3">{videoName}.mp4</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="flex items-center space-x-2 text-grey-light/70">
                <ImageIcon className="w-4 h-4 text-cyan/70" />
                <span>{imageCount} images</span>
              </div>
              <div className="flex items-center space-x-2 text-grey-light/70">
                <Settings className="w-4 h-4 text-purple/70" />
                <span>Medium quality</span>
              </div>
            </div>
          </div>

          {/* Progress Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-grey-light/70">Progress</span>
              <span className="text-white font-mono">{Math.round(progress)}%</span>
            </div>
            
            <Progress 
              value={progress} 
              className="h-3 bg-purple-muted/20"
            />

            <div className="flex items-center space-x-3">
              <Loader2 className="w-4 h-4 text-cyan animate-spin" />
              <span className="text-white font-medium">{currentStep}</span>
            </div>
          </div>

          {/* Time Info */}
          <div className="flex items-center justify-between p-3 bg-purple/10 rounded-xl border border-purple/20">
            <div className="flex items-center space-x-2 text-sm text-grey-light/70">
              <Clock className="w-4 h-4" />
              <span>Elapsed: {formatTime(elapsedTime)}</span>
            </div>
            <div className="text-sm text-grey-light/70">
              Est. total: ~{formatTime(estimatedDuration)}
            </div>
          </div>

          {/* Processing Steps */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-white">Processing Steps</h4>
            <div className="space-y-1">
              {steps.map((step, index) => {
                const isCompleted = progress > ((index + 1) / steps.length) * 95
                const isCurrent = currentStep === step.label
                
                return (
                  <div 
                    key={index}
                    className={`flex items-center space-x-2 text-xs p-2 rounded-lg transition-all duration-300 ${
                      isCurrent 
                        ? 'bg-cyan/10 border border-cyan/20 text-cyan' 
                        : isCompleted
                        ? 'bg-success/10 border border-success/20 text-success'
                        : 'bg-grey-light/5 text-grey-light/50'
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full ${
                      isCurrent 
                        ? 'bg-cyan animate-pulse' 
                        : isCompleted
                        ? 'bg-success'
                        : 'bg-grey-light/30'
                    }`} />
                    <span>{step.label}</span>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="text-center text-sm text-grey-light/60">
            Please wait while we process your timelapse...
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
