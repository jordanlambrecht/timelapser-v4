// src/app/overlays/page.tsx
"use client"

import { OverlayPresetsCard } from "./components/overlay-presets-card"

export default function Overlays() {
  return (
    <div className='max-w-4xl mx-auto space-y-8'>
      {/* Header */}
      <div className='space-y-4'>
        <div>
          <h1 className='text-4xl font-bold gradient-text'>Overlay Management</h1>
          <p className='mt-2 text-muted-foreground'>
            Create and manage overlay presets for your timelapses. Configure text, weather data, and image overlays with custom positioning.
          </p>
        </div>
      </div>

      {/* Overlay Presets Management */}
      <OverlayPresetsCard />
    </div>
  )
}