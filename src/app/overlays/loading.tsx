// src/app/overlays/loading.tsx
"use client"

import { PageLoader } from "@/components/ui/page-loader"

/**
 * Overlays page loading component
 * 
 * This is automatically shown by Next.js during overlays page navigation
 * and provides overlay-specific loading messages.
 */
const OverlaysLoading = () => {
  return (
    <PageLoader 
      title="Loading overlay management..."
      subtitle="Fetching overlay presets and configurations"
    />
  )
}

export default OverlaysLoading