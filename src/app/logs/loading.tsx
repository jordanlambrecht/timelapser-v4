// src/app/logs/loading.tsx
"use client"

import { PageLoader } from "@/components/ui/page-loader"

/**
 * Logs page loading component
 *
 * This is automatically shown by Next.js during logs page navigation
 * and provides logs-specific loading messages.
 */
const LogsLoading = () => {
  return (
    <PageLoader title='Loading logs...' subtitle='Fetching system log data' />
  )
}

export default LogsLoading
