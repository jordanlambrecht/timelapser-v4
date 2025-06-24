// src/components/video-generation-modal/index.tsx
"use client"

import { useState } from "react"
import { X, Video, Settings, Palette } from "lucide-react"
import { VideoOverlayConfig, OverlaySettings } from "../video-overlay-config"
import { Camera } from "@/types"

interface VideoGenerationModalProps {
  isOpen: boolean
  onClose: () => void
  camera: Camera
  onGenerate: (settings: VideoModalSettings) => void
}

export interface VideoModalSettings {
  video_name?: string
  framerate: number
  quality: "low" | "medium" | "high"
  overlay_settings: OverlaySettings
  day_start?: number
  day_end?: number
}

export function VideoGenerationModal({
  isOpen,
  onClose,
  camera,
  onGenerate,
}: VideoGenerationModalProps) {
  const [currentTab, setCurrentTab] = useState<
    "basic" | "overlay" | "advanced"
  >("basic")
  const [generating, setGenerating] = useState(false)

  const [settings, setSettings] = useState<VideoModalSettings>({
    video_name: "",
    framerate: 30,
    quality: "medium",
    overlay_settings: {
      enabled: true,
      position: "bottom-right",
      font_size: 48,
      font_color: "white",
      background_color: "black@0.5",
      format: "Day {day}",
    },
    day_start: undefined,
    day_end: undefined,
  })

  if (!isOpen) return null

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await onGenerate(settings)
      onClose()
    } catch (error) {
      console.error("Video generation failed:", error)
    } finally {
      setGenerating(false)
    }
  }

  const getQualityDescription = (quality: string) => {
    const descriptions = {
      low: "720p - Fast generation, smaller files",
      medium: "1080p - Balanced quality and size",
      high: "Original resolution - Best quality, larger files",
    }
    return descriptions[quality as keyof typeof descriptions]
  }

  const tabs = [
    { id: "basic", label: "Basic Settings", icon: Video },
    { id: "overlay", label: "Day Overlays", icon: Palette },
    { id: "advanced", label: "Advanced", icon: Settings },
  ]

  return (
    <div className='fixed inset-0 z-50 overflow-y-auto'>
      <div className='flex items-center justify-center min-h-screen p-4'>
        <div
          className='fixed inset-0 transition-opacity bg-black bg-opacity-50'
          onClick={onClose}
        />

        <div className='relative w-full max-w-4xl bg-gray-800 shadow-2xl rounded-2xl'>
          {/* Header */}
          <div className='flex items-center justify-between p-6 border-b border-gray-700'>
            <div>
              <h2 className='text-2xl font-bold text-white'>
                Generate Timelapse Video
              </h2>
              <p className='mt-1 text-gray-400'>
                Create a video from {camera.name}
              </p>
            </div>
            <button
              onClick={onClose}
              className='p-2 text-gray-400 transition-colors rounded-lg hover:text-white hover:bg-gray-700'
            >
              <X className='w-6 h-6' />
            </button>
          </div>

          {/* Tab Navigation */}
          <div className='flex border-b border-gray-700'>
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setCurrentTab(tab.id as any)}
                  className={`flex items-center gap-2 px-6 py-4 font-medium transition-colors ${
                    currentTab === tab.id
                      ? "text-blue-400 border-b-2 border-blue-400 bg-gray-750"
                      : "text-gray-400 hover:text-white hover:bg-gray-750"
                  }`}
                >
                  <Icon className='w-4 h-4' />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Tab Content */}
          <div className='p-6 overflow-y-auto max-h-96'>
            {currentTab === "basic" && (
              <div className='space-y-6'>
                {/* Video Name */}
                <div>
                  <label className='block mb-2 text-sm font-medium text-white'>
                    Video Name (Optional)
                  </label>
                  <input
                    type='text'
                    value={settings.video_name}
                    onChange={(e) =>
                      setSettings((prev) => ({
                        ...prev,
                        video_name: e.target.value,
                      }))
                    }
                    placeholder={`${
                      camera.name
                    }_timelapse_${new Date().getFullYear()}`}
                    className='w-full px-4 py-3 text-white placeholder-gray-400 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
                  />
                  <p className='mt-1 text-xs text-gray-400'>
                    Leave empty for automatic naming with timestamp
                  </p>
                </div>

                {/* Quality */}
                <div>
                  <label className='block mb-3 text-sm font-medium text-white'>
                    Video Quality
                  </label>
                  <div className='grid grid-cols-1 gap-3 md:grid-cols-3'>
                    {(["low", "medium", "high"] as const).map((quality) => (
                      <label
                        key={quality}
                        className={`relative flex flex-col p-4 border-2 rounded-lg cursor-pointer transition-all ${
                          settings.quality === quality
                            ? "border-blue-500 bg-blue-500/10"
                            : "border-gray-600 hover:border-gray-500"
                        }`}
                      >
                        <input
                          type='radio'
                          name='quality'
                          value={quality}
                          checked={settings.quality === quality}
                          onChange={(e) =>
                            setSettings((prev) => ({
                              ...prev,
                              quality: e.target.value as any,
                            }))
                          }
                          className='sr-only'
                        />
                        <div className='flex items-center justify-between mb-2'>
                          <span className='font-medium text-white capitalize'>
                            {quality}
                          </span>
                          {settings.quality === quality && (
                            <div className='w-2 h-2 bg-blue-500 rounded-full' />
                          )}
                        </div>
                        <span className='text-xs text-gray-400'>
                          {getQualityDescription(quality)}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Framerate */}
                <div>
                  <label className='block mb-2 text-sm font-medium text-white'>
                    Framerate: {settings.framerate} FPS
                  </label>
                  <input
                    type='range'
                    min='15'
                    max='60'
                    step='5'
                    value={settings.framerate}
                    onChange={(e) =>
                      setSettings((prev) => ({
                        ...prev,
                        framerate: parseInt(e.target.value),
                      }))
                    }
                    className='w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer'
                  />
                  <div className='flex justify-between mt-1 text-xs text-gray-400'>
                    <span>15 FPS (Slow)</span>
                    <span>30 FPS (Standard)</span>
                    <span>60 FPS (Smooth)</span>
                  </div>
                  <p className='mt-2 text-xs text-gray-400'>
                    Higher framerates create smoother motion but larger file
                    sizes
                  </p>
                </div>
              </div>
            )}

            {currentTab === "overlay" && (
              <VideoOverlayConfig
                settings={settings.overlay_settings}
                onChange={(overlaySettings) =>
                  setSettings((prev) => ({
                    ...prev,
                    overlay_settings: overlaySettings,
                  }))
                }
                showPreview={true}
              />
            )}

            {currentTab === "advanced" && (
              <div className='space-y-6'>
                <div>
                  <h3 className='mb-4 text-lg font-semibold text-white'>
                    Day Range Selection
                  </h3>
                  <p className='mb-4 text-sm text-gray-400'>
                    Generate video from specific day range (leave empty for all
                    days)
                  </p>

                  <div className='grid grid-cols-2 gap-4'>
                    <div>
                      <label className='block mb-2 text-sm font-medium text-white'>
                        Start Day (Optional)
                      </label>
                      <input
                        type='number'
                        min='1'
                        value={settings.day_start || ""}
                        onChange={(e) =>
                          setSettings((prev) => ({
                            ...prev,
                            day_start: e.target.value
                              ? parseInt(e.target.value)
                              : undefined,
                          }))
                        }
                        placeholder='1'
                        className='w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
                      />
                    </div>

                    <div>
                      <label className='block mb-2 text-sm font-medium text-white'>
                        End Day (Optional)
                      </label>
                      <input
                        type='number'
                        min='1'
                        value={settings.day_end || ""}
                        onChange={(e) =>
                          setSettings((prev) => ({
                            ...prev,
                            day_end: e.target.value
                              ? parseInt(e.target.value)
                              : undefined,
                          }))
                        }
                        placeholder='30'
                        className='w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
                      />
                    </div>
                  </div>

                  <div className='p-4 mt-4 border rounded-lg bg-blue-900/20 border-blue-700/30'>
                    <h4 className='mb-2 text-sm font-medium text-blue-300'>
                      Examples:
                    </h4>
                    <ul className='space-y-1 text-xs text-blue-200'>
                      <li>• Days 1-30: First month of construction</li>
                      <li>
                        • Days 10-50: Skip initial setup, focus on main build
                      </li>
                      <li>• Day 1 only: Single day progression</li>
                      <li>
                        • No range: Complete timelapse from all captured days
                      </li>
                    </ul>
                  </div>
                </div>

                {/* File Size Estimation */}
                <div className='p-4 rounded-lg bg-gray-700/50'>
                  <h4 className='mb-2 text-sm font-medium text-white'>
                    Estimated Output:
                  </h4>
                  <div className='space-y-1 text-xs text-gray-300'>
                    <div>
                      Quality: {settings.quality} →{" "}
                      {getQualityDescription(settings.quality)}
                    </div>
                    <div>Framerate: {settings.framerate} FPS</div>
                    <div>
                      Overlays:{" "}
                      {settings.overlay_settings.enabled
                        ? "Enabled"
                        : "Disabled"}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className='flex items-center justify-between p-6 border-t border-gray-700'>
            <div className='text-sm text-gray-400'>
              {settings.overlay_settings.enabled && (
                <span className='flex items-center gap-2'>
                  <Palette className='w-4 h-4' />
                  Day overlays enabled
                </span>
              )}
            </div>

            <div className='flex gap-3'>
              <button
                onClick={onClose}
                className='px-6 py-2 text-gray-400 transition-colors hover:text-white'
              >
                Cancel
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className='flex items-center gap-2 px-6 py-2 font-medium text-white transition-colors bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed'
              >
                <Video className='w-4 h-4' />
                {generating ? "Generating..." : "Generate Video"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
