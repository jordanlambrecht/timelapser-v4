// src/app/cameras/[id]/loading.tsx
"use client"

import { PageLoader } from "@/components/ui/page-loader"

/**
 * Camera details page loading component
 *
 * This is automatically shown by Next.js during camera details page navigation
 * and provides camera-specific loading messages.
 */
const CameraDetailsLoading = () => {
  return (
    <PageLoader
      title='Loading camera details...'
      subtitle='Fetching camera configuration and latest images'
    />
  )
}

export default CameraDetailsLoading
