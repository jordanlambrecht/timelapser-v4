// src/app/overlays/create/page.tsx
"use client"

import { OverlayManagement } from "../components/overlay-management-full"

export default function CreateOverlay() {
  return (
    <div className='max-w-7xl mx-auto space-y-8'>
      {/* Header */}
      {/* <div className='space-y-4'>
        <div>
          <h1 className='text-4xl font-bold gradient-text'>Create Overlay</h1>
          <p className='mt-2 text-muted-foreground'>
            Create and configure overlay presets with live preview. Configure text, weather data, and image overlays with custom positioning.
          </p>
        </div>
      </div> */}

      {/* Overlay Management Interface */}
      <OverlayManagement />
    </div>
  )
}
