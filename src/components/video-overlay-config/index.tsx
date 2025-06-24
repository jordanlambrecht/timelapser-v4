// src/components/video-overlay-config/index.tsx
"use client"

import { useState } from "react"
import type { OverlaySettings, VideoOverlayConfigProps } from "@/types"

// Re-export OverlaySettings for backwards compatibility
export type { OverlaySettings } from "@/types"

export function VideoOverlayConfig({
  settings,
  onChange,
  showPreview = true,
}: VideoOverlayConfigProps) {
  const [previewDay, setPreviewDay] = useState(47)

  const handleChange = (field: keyof OverlaySettings, value: any) => {
    onChange({
      ...settings,
      [field]: value,
    })
  }

  const getPreviewText = () => {
    return settings.format.replace("{day}", previewDay.toString())
  }

  const getPositionDescription = (position: string) => {
    const descriptions = {
      "top-left": "Top Left Corner",
      "top-right": "Top Right Corner",
      "bottom-left": "Bottom Left Corner",
      "bottom-right": "Bottom Right Corner",
      center: "Center of Video",
    }
    return descriptions[position as keyof typeof descriptions] || position
  }

  return (
    <div className='space-y-6'>
      {/* Enable/Disable Toggle */}
      <div className='flex items-center justify-between'>
        <div>
          <h3 className='text-lg font-semibold text-white'>Day Overlays</h3>
          <p className='text-sm text-gray-400'>
            Add day progression text to your timelapse
          </p>
        </div>
        <label className='relative inline-flex items-center cursor-pointer'>
          <input
            type='checkbox'
            checked={settings.enabled}
            onChange={(e) => handleChange("enabled", e.target.checked)}
            className='sr-only peer'
          />
          <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
        </label>
      </div>

      {settings.enabled && (
        <div className='grid grid-cols-1 gap-6 md:grid-cols-2'>
          {/* Left Column - Settings */}
          <div className='space-y-4'>
            {/* Position */}
            <div>
              <label className='block mb-2 text-sm font-medium text-white'>
                Position
              </label>
              <select
                value={settings.position}
                onChange={(e) => handleChange("position", e.target.value)}
                className='w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
              >
                <option value='top-left'>Top Left</option>
                <option value='top-right'>Top Right</option>
                <option value='bottom-left'>Bottom Left</option>
                <option value='bottom-right'>Bottom Right</option>
                <option value='center'>Center</option>
              </select>
              <p className='mt-1 text-xs text-gray-400'>
                {getPositionDescription(settings.position)}
              </p>
            </div>

            {/* Text Format */}
            <div>
              <label className='block mb-2 text-sm font-medium text-white'>
                Text Format
              </label>
              <input
                type='text'
                value={settings.format}
                onChange={(e) => handleChange("format", e.target.value)}
                placeholder='Day {day}'
                className='w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
              />
              <p className='mt-1 text-xs text-gray-400'>
                Use {`{day}`} for day number. Example: "Day {`{day}`}", "Day{" "}
                {`{day}`} of Construction"
              </p>
            </div>

            {/* Font Size */}
            <div>
              <label className='block mb-2 text-sm font-medium text-white'>
                Font Size: {settings.font_size}px
              </label>
              <input
                type='range'
                min='24'
                max='96'
                step='4'
                value={settings.font_size}
                onChange={(e) =>
                  handleChange("font_size", parseInt(e.target.value))
                }
                className='w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer'
              />
              <div className='flex justify-between mt-1 text-xs text-gray-400'>
                <span>Small</span>
                <span>Large</span>
              </div>
            </div>

            {/* Colors */}
            <div className='grid grid-cols-2 gap-4'>
              <div>
                <label className='block mb-2 text-sm font-medium text-white'>
                  Text Color
                </label>
                <div className='flex gap-2'>
                  <input
                    type='color'
                    value={
                      settings.font_color === "white"
                        ? "#ffffff"
                        : settings.font_color
                    }
                    onChange={(e) => handleChange("font_color", e.target.value)}
                    className='w-12 h-10 bg-gray-700 border border-gray-600 rounded cursor-pointer'
                  />
                  <select
                    value={settings.font_color}
                    onChange={(e) => handleChange("font_color", e.target.value)}
                    className='flex-1 px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500'
                  >
                    <option value='white'>White</option>
                    <option value='black'>Black</option>
                    <option value='yellow'>Yellow</option>
                    <option value='red'>Red</option>
                    <option value='cyan'>Cyan</option>
                  </select>
                </div>
              </div>

              <div>
                <label className='block mb-2 text-sm font-medium text-white'>
                  Background
                </label>
                <select
                  value={settings.background_color}
                  onChange={(e) =>
                    handleChange("background_color", e.target.value)
                  }
                  className='w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500'
                >
                  <option value='none'>None</option>
                  <option value='black@0.3'>Light Shadow</option>
                  <option value='black@0.5'>Medium Shadow</option>
                  <option value='black@0.8'>Dark Shadow</option>
                  <option value='black'>Solid Black</option>
                </select>
              </div>
            </div>
          </div>

          {/* Right Column - Preview */}
          {showPreview && (
            <div className='space-y-4'>
              <div>
                <label className='block mb-2 text-sm font-medium text-white'>
                  Preview
                </label>

                {/* Preview Video Frame */}
                <div className='relative overflow-hidden bg-gray-800 border border-gray-600 rounded-lg aspect-video'>
                  {/* Simulated video background */}
                  <div className='absolute inset-0 opacity-50 bg-gradient-to-br from-blue-900 to-purple-900' />
                  <div className='absolute inset-0 flex items-center justify-center'>
                    <div className='text-4xl text-gray-500'>📹</div>
                  </div>

                  {/* Overlay Preview */}
                  <div
                    className={`absolute text-white font-bold ${
                      settings.position === "top-left"
                        ? "top-4 left-4"
                        : settings.position === "top-right"
                        ? "top-4 right-4"
                        : settings.position === "bottom-left"
                        ? "bottom-4 left-4"
                        : settings.position === "bottom-right"
                        ? "bottom-4 right-4"
                        : "top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"
                    }`}
                    style={{
                      fontSize: `${Math.max(12, settings.font_size / 4)}px`,
                      color: settings.font_color,
                      backgroundColor:
                        settings.background_color === "none"
                          ? "transparent"
                          : settings.background_color.includes("@")
                          ? `rgba(0, 0, 0, ${
                              settings.background_color.split("@")[1]
                            })`
                          : settings.background_color,
                      padding:
                        settings.background_color !== "none" ? "4px 8px" : "0",
                      borderRadius:
                        settings.background_color !== "none" ? "4px" : "0",
                    }}
                  >
                    {getPreviewText()}
                  </div>
                </div>

                {/* Preview Day Controller */}
                <div className='mt-3'>
                  <label className='block mb-1 text-xs text-gray-400'>
                    Preview Day: {previewDay}
                  </label>
                  <input
                    type='range'
                    min='1'
                    max='100'
                    value={previewDay}
                    onChange={(e) => setPreviewDay(parseInt(e.target.value))}
                    className='w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer'
                  />
                </div>
              </div>

              {/* Format Examples */}
              <div>
                <label className='block mb-2 text-sm font-medium text-white'>
                  Format Examples
                </label>
                <div className='space-y-1 text-xs'>
                  <div className='text-gray-300'>
                    <code className='px-2 py-1 bg-gray-700 rounded'>
                      Day {`{day}`}
                    </code>
                    <span className='ml-2 text-gray-400'>→ Day 47</span>
                  </div>
                  <div className='text-gray-300'>
                    <code className='px-2 py-1 bg-gray-700 rounded'>{`{day}`}</code>
                    <span className='ml-2 text-gray-400'>→ 47</span>
                  </div>
                  <div className='text-gray-300'>
                    <code className='px-2 py-1 bg-gray-700 rounded'>
                      Day {`{day}`} of Project
                    </code>
                    <span className='ml-2 text-gray-400'>
                      → Day 47 of Project
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
