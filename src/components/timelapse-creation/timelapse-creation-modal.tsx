// src/components/timelapse-creation/timelapse-creation-modal.tsx
"use client"

import { useState, useEffect } from "react"
import { useAutoAnimate } from "@formkit/auto-animate/react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { TimelapseConfigurationSlide } from "./slides/timelapse-configuration-slide"
import { CaptureIntervalSlide } from "./slides/capture-interval-slide"
import { VideoAutomationSlide } from "./slides/video-automation-slide"
import { RenderSettingsSlide } from "./slides/render-settings-slide"
import { OverlaysSlide } from "./slides/overlays-slide"

export interface TimelapseForm {
  name: string
  runWindowEnabled: boolean
  runWindowType: "between" | "sunrise-sunset"
  timeWindowStart: string
  timeWindowEnd: string
  sunriseOffsetMinutes: number
  sunsetOffsetMinutes: number
  stopTimeEnabled: boolean
  stopType: "datetime" | "daycount"
  stopDateTime: string
  stopDayCount: number
  captureInterval: number
  // Video automation fields
  videoManualOnly: boolean
  videoPerCapture: boolean
  videoScheduled: boolean
  videoScheduleType: "daily" | "weekly"
  videoScheduleTime: string
  videoScheduleDays: number[]
  videoScheduleOverwrite: boolean
  videoMilestone: boolean
  videoMilestoneInterval: number
  videoMilestoneOverwrite: boolean
  // Video render settings
  videoGenerationMode: "standard" | "target"
  videoStandardFps: number
  videoEnableTimeLimits: boolean
  videoMinDuration: number
  videoMaxDuration: number
  videoTargetDuration: number
  videoFpsMin: number
  videoFpsMax: number
  videoQuality: "low" | "medium" | "high"
  // Overlay settings
  overlayEnabled: boolean
  overlayPresetId: number | null
}

interface TimelapseCreationModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (form: TimelapseForm, cameraId?: number) => void
  cameraId?: number // Optional: specify which camera to create timelapse for
}

export function TimelapseCreationModal({
  isOpen,
  onClose,
  onSubmit,
  cameraId,
}: TimelapseCreationModalProps) {
  const [currentSlide, setCurrentSlide] = useState(0)
  const [form, setForm] = useState<TimelapseForm>({
    name: "",
    runWindowEnabled: false,
    runWindowType: "between",
    timeWindowStart: "06:00",
    timeWindowEnd: "18:00",
    sunriseOffsetMinutes: 45,
    sunsetOffsetMinutes: -45,
    stopTimeEnabled: false,
    stopType: "datetime",
    stopDateTime: "",
    stopDayCount: 1,
    captureInterval: 300, // Default to 5 minutes
    // Video automation defaults
    videoManualOnly: true,
    videoPerCapture: false,
    videoScheduled: false,
    videoScheduleType: "daily",
    videoScheduleTime: "18:00",
    videoScheduleDays: [1], // Default to Monday
    videoScheduleOverwrite: false,
    videoMilestone: false,
    videoMilestoneInterval: 500,
    videoMilestoneOverwrite: false,
    // Video render settings defaults
    videoGenerationMode: "standard",
    videoStandardFps: 30,
    videoEnableTimeLimits: false,
    videoMinDuration: 5,
    videoMaxDuration: 60,
    videoTargetDuration: 30,
    videoFpsMin: 15,
    videoFpsMax: 60,
    videoQuality: "medium",
    // Overlay defaults
    overlayEnabled: true,
    overlayPresetId: null,
  })

  // AutoAnimate refs
  const [slideContentRef] = useAutoAnimate({ duration: 300 })
  const [progressRef] = useAutoAnimate({ duration: 200 })
  const [footerRef] = useAutoAnimate({ duration: 250 })

  // Helper function to update form state
  const updateForm = (updates: Partial<TimelapseForm>) => {
    setForm(prev => ({ ...prev, ...updates }))
  }

  // Get minimum datetime for datetime input (current time)
  const getMinDateTime = () => {
    const now = new Date()
    return now.toISOString().slice(0, 16)
  }

  // Initialize form with default values when modal opens
  useEffect(() => {
    if (isOpen) {
      const now = new Date()
      const dateStr = now.toISOString().slice(0, 10)
      const timeStr = now.toTimeString().slice(0, 5).replace(":", "")
      const defaultName = `Timelapse ${dateStr} ${timeStr}`
      
      // Default stop date to tomorrow
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      const defaultStopDateTime = tomorrow.toISOString().slice(0, 16)
      
      setForm({
        name: defaultName,
        runWindowEnabled: false,
        runWindowType: "between",
        timeWindowStart: "06:00",
        timeWindowEnd: "18:00",
        sunriseOffsetMinutes: 45,
        sunsetOffsetMinutes: -45,
        stopTimeEnabled: false,
        stopType: "datetime",
        stopDateTime: defaultStopDateTime,
        stopDayCount: 1,
        captureInterval: 300, // Default to 5 minutes
        // Video automation defaults
        videoManualOnly: true,
        videoPerCapture: false,
        videoScheduled: false,
        videoScheduleType: "daily",
        videoScheduleTime: "18:00",
        videoScheduleDays: [1], // Default to Monday
        videoScheduleOverwrite: false,
        videoMilestone: false,
        videoMilestoneInterval: 500,
        videoMilestoneOverwrite: false,
        // Video render settings defaults
        videoGenerationMode: "standard",
        videoStandardFps: 30,
        videoEnableTimeLimits: false,
        videoMinDuration: 5,
        videoMaxDuration: 60,
        videoTargetDuration: 30,
        videoFpsMin: 15,
        videoFpsMax: 60,
        videoQuality: "medium",
        // Overlay defaults
        overlayEnabled: true,
        overlayPresetId: null,
      })
    }
  }, [isOpen])

  const handleClose = () => {
    onClose()
    setCurrentSlide(0)
  }

  const handleNext = () => {
    if (currentSlide < 4) {
      setCurrentSlide(currentSlide + 1)
    } else {
      // Handle timelapse start
      onSubmit(form, cameraId)
      handleClose()
    }
  }

  const handleBack = () => {
    if (currentSlide > 0) {
      setCurrentSlide(currentSlide - 1)
    }
  }

  const renderSlide = () => {
    switch (currentSlide) {
      case 0:
        return (
          <TimelapseConfigurationSlide
            form={form}
            updateForm={updateForm}
            getMinDateTime={getMinDateTime}
          />
        )
      case 1:
        return (
          <CaptureIntervalSlide
            form={form}
            updateForm={updateForm}
          />
        )
      case 2:
        return (
          <VideoAutomationSlide
            form={form}
            updateForm={updateForm}
          />
        )
      case 3:
        return (
          <RenderSettingsSlide
            form={form}
            updateForm={updateForm}
          />
        )
      case 4:
        return (
          <OverlaysSlide
            form={form}
            updateForm={updateForm}
          />
        )
      default:
        return null
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="w-[95vw] max-w-[400px] sm:max-w-[600px] md:max-w-[700px] lg:max-w-[800px] xl:max-w-[900px] glass-heavy border-purple-muted/30 overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold text-white">
            Create New Timelapse
          </DialogTitle>
        </DialogHeader>
        
        {/* Progress Indicators */}
        <div ref={progressRef} className="flex justify-center gap-2 py-2">
          {[0, 1, 2, 3, 4].map((index) => (
            <div
              key={index}
              className={cn(
                "h-1 w-20 rounded-full transition-all duration-300",
                currentSlide === index
                  ? "bg-gradient-to-r from-purple to-cyan"
                  : currentSlide > index
                  ? "bg-purple-light/50"
                  : "bg-purple-muted/30"
              )}
            />
          ))}
        </div>
        
        {/* Slide Content */}
        <div ref={slideContentRef} className="py-6 min-h-[200px] overflow-hidden">
          {renderSlide()}
        </div>

        <DialogFooter className="flex justify-between sm:justify-between">
          <Button
            variant="outline"
            onClick={handleClose}
            className="border-purple-muted/30 text-grey-light hover:bg-purple-dark hover:border-purple-muted hover:text-white"
          >
            Cancel
          </Button>
          <div ref={footerRef} className="flex gap-3">
            {currentSlide > 0 && (
              <Button
                variant="outline"
                onClick={handleBack}
                className="border-purple-muted/30 text-grey-light hover:bg-purple-dark hover:border-purple-muted hover:text-white"
              >
                Back
              </Button>
            )}
            <Button
              onClick={handleNext}
              className="bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90 text-white font-medium"
            >
              {currentSlide === 4 ? "Start" : "Next"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}