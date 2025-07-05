// src/app/settings/loading.tsx
"use client"

import { PageLoader } from "@/components/ui/page-loader"

/**
 * Settings page loading component
 * 
 * This is automatically shown by Next.js during settings page navigation
 * and provides settings-specific loading messages.
 */
const SettingsLoading = () => {
  return (
    <PageLoader 
      title="Loading settings..."
      subtitle="Fetching configuration data"
    />
  )
}

export default SettingsLoading
