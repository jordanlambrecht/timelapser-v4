// src/app/loading.tsx
"use client"

import { PageLoader } from "@/components/ui/page-loader"

/**
 * Default app-level loading component
 *
 * This is automatically shown by Next.js during page navigation.
 * Individual pages can import PageLoader directly for custom messaging.
 */
const Loading = () => {
  return (
    <PageLoader title='Loading dashboard...' subtitle='Fetching camera data' />
  )
}

export default Loading
