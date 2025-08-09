"use client"

import { useState } from "react"
import { useTimelapseLibrary } from "@/hooks/use-timelapse-library"
import { useMultiselect } from "@/hooks/use-multiselect"
import { useBatchOverlayOperations } from "@/hooks/use-batch-overlay-operations"
import { Card } from "@/components/ui/card"
import { StatsDashboard } from "@/components/timelapse-library/stats-dashboard"
import { LibraryHeader } from "@/components/timelapse-library/library-header"
import { TimelapseGrid } from "@/components/timelapse-library/timelapse-grid"
import { BulkActionsDrawer } from "@/components/timelapse-library/bulk-actions-drawer"
import { Video, Search } from "lucide-react"

export type ViewMode = "card" | "row"
export type SortBy = "camera" | "alphabetical" | "chronological"

export default function TimelapsesLibraryPage() {
  // View state
  const [viewMode, setViewMode] = useState<ViewMode>("card")
  const [sortBy, setSortBy] = useState<SortBy>("camera")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
  const [starredOnly, setStarredOnly] = useState(false)

  // Data fetching
  const {
    timelapses,
    statistics,
    loading,
    error,
    statisticsError,
    refetch
  } = useTimelapseLibrary({
    sortBy,
    sortOrder,
    starredOnly,
    includeActive: true
  })

  // Multiselect state
  const {
    selectedIds,
    isSelected,
    selectItem,
    deselectItem,
    selectAll,
    clearSelection,
    hasSelection
  } = useMultiselect<number>()

  // Batch overlay operations
  const { isProcessing: isProcessingOverlays, reprocessOverlays } = useBatchOverlayOperations()

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode)
  }

  const handleSortChange = (sort: SortBy, order: "asc" | "desc") => {
    setSortBy(sort)
    setSortOrder(order)
  }

  const handleStarredFilter = (starred: boolean) => {
    setStarredOnly(starred)
  }

  const handleBulkAction = async (action: string, selectedIds?: number[]) => {
    if (!selectedIds || selectedIds.length === 0) {
      return
    }

    switch (action) {
      case 'regenerate-overlays':
        await reprocessOverlays(selectedIds)
        break
      case 'delete':
        // TODO: Implement bulk delete
        console.log('Bulk delete:', selectedIds)
        break
      case 'star':
        // TODO: Implement bulk star
        console.log('Bulk star:', selectedIds)
        break
      case 'download':
        // TODO: Implement bulk download
        console.log('Bulk download:', selectedIds)
        break
      default:
        console.log(`Unknown bulk action: ${action}`, selectedIds)
    }
  }

  if (loading) {
    return (
      <div className="relative space-y-8">
        {/* Page Header Skeleton */}
        <div className="space-y-4">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-purple/20 animate-pulse" />
            <div className="space-y-2">
              <div className="h-8 w-64 bg-purple/20 rounded animate-pulse" />
              <div className="h-4 w-32 bg-purple/10 rounded animate-pulse" />
            </div>
          </div>
        </div>

        {/* Stats Dashboard Skeleton */}
        <div className="glass p-6 rounded-2xl">
          <div className="h-20 bg-purple/10 rounded-xl animate-pulse" />
        </div>

        {/* Header Controls Skeleton */}
        <div className="glass p-4 rounded-xl">
          <div className="flex justify-between items-center">
            <div className="flex space-x-4">
              <div className="h-8 w-32 bg-purple/10 rounded animate-pulse" />
              <div className="h-8 w-24 bg-purple/10 rounded animate-pulse" />
            </div>
            <div className="h-8 w-20 bg-purple/10 rounded animate-pulse" />
          </div>
        </div>

        {/* Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="glass p-4 rounded-xl space-y-4">
              <div className="aspect-video bg-purple/10 rounded-lg animate-pulse" />
              <div className="space-y-2">
                <div className="h-4 bg-purple/10 rounded animate-pulse" />
                <div className="h-3 w-2/3 bg-purple/10 rounded animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="relative space-y-8">
        <div className="flex items-center justify-center min-h-[40vh]">
          <div className="glass-strong p-8 rounded-2xl text-center max-w-md">
            <div className="w-16 h-16 mx-auto mb-4 bg-failure/20 rounded-xl flex items-center justify-center">
              <Search className="w-8 h-8 text-failure" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              Unable to Load Library
            </h2>
            <p className="text-grey-light/70 mb-6">{error}</p>
            <button 
              onClick={refetch}
              className="px-6 py-3 bg-gradient-to-r from-pink to-cyan text-black font-medium rounded-xl hover:shadow-lg transition-all duration-300"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="p-3 bg-gradient-to-br from-purple/30 to-cyan/30 rounded-xl border border-purple-muted/40">
            <Video className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-4xl font-bold gradient-text">
              Timelapse Library
            </h1>
            <p className="text-grey-light/70 mt-1">
              {statisticsError 
                ? `${timelapses.length} timelapses shown` 
                : `${statistics?.total_timelapses || 0} timelapses total`
              }
            </p>
          </div>
        </div>
      </div>

      {/* Statistics Dashboard */}
      <StatsDashboard statistics={statistics || undefined} error={statisticsError} />

      {/* Library Controls */}
      <LibraryHeader
        viewMode={viewMode}
        sortBy={sortBy}
        sortOrder={sortOrder}
        starredOnly={starredOnly}
        onViewModeChange={handleViewModeChange}
        onSortChange={handleSortChange}
        onStarredFilter={handleStarredFilter}
        hasSelection={hasSelection}
        selectedCount={selectedIds.length}
        onSelectAll={() => selectAll(timelapses.map(t => t.id))}
        onClearSelection={clearSelection}
      />

      {/* Main Content */}
      <TimelapseGrid
        timelapses={timelapses}
        viewMode={viewMode}
        sortBy={sortBy}
        selectedIds={selectedIds}
        onSelect={selectItem}
        onDeselect={deselectItem}
        isSelected={isSelected}
      />

      {/* Bulk Actions Drawer */}
      <BulkActionsDrawer
        show={hasSelection}
        selectedIds={selectedIds}
        selectedCount={selectedIds.length}
        onClearSelection={clearSelection}
        onBulkAction={handleBulkAction}
        isProcessingOverlays={isProcessingOverlays}
      />
    </div>
  )
}
