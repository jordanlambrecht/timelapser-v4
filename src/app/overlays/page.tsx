// src/app/overlays/page.tsx
"use client"

import { OverlayPresetsCard } from "./components/overlay-presets-card"

export default function Overlays() {
  return (
    <div className='max-w-7xl mx-auto space-y-8'>
      {/* Header */}
      <div className='space-y-4'>
        <div>
          <h1 className='text-4xl font-bold gradient-text'>Overlay Library</h1>
          <p className='mt-2 text-muted-foreground'>
            Browse, manage, and create overlay presets for your timelapses. Save configurations to reuse across multiple projects.
          </p>
        </div>
      </div>

      {/* Overlay Library Interface */}
      <OverlayPresetsCard />
    </div>
  )
}