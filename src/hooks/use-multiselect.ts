import { useState, useCallback } from "react"

/**
 * Generic multiselect hook for managing selection state
 */
export function useMultiselect<T = string | number>() {
  const [selectedIds, setSelectedIds] = useState<Set<T>>(new Set())

  const isSelected = useCallback((id: T): boolean => {
    return selectedIds.has(id)
  }, [selectedIds])

  const selectItem = useCallback((id: T) => {
    setSelectedIds(prev => new Set([...prev, id]))
  }, [])

  const deselectItem = useCallback((id: T) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev)
      newSet.delete(id)
      return newSet
    })
  }, [])

  const toggleItem = useCallback((id: T) => {
    if (isSelected(id)) {
      deselectItem(id)
    } else {
      selectItem(id)
    }
  }, [isSelected, selectItem, deselectItem])

  const selectAll = useCallback((ids: T[]) => {
    setSelectedIds(new Set(ids))
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const selectRange = useCallback((startId: T, endId: T, allIds: T[]) => {
    const startIndex = allIds.indexOf(startId)
    const endIndex = allIds.indexOf(endId)
    
    if (startIndex === -1 || endIndex === -1) return

    const start = Math.min(startIndex, endIndex)
    const end = Math.max(startIndex, endIndex)
    const rangeIds = allIds.slice(start, end + 1)
    
    setSelectedIds(prev => new Set([...prev, ...rangeIds]))
  }, [])

  const hasSelection = selectedIds.size > 0
  const selectedCount = selectedIds.size
  const selectedIdsArray = Array.from(selectedIds)

  return {
    selectedIds: selectedIdsArray,
    selectedCount,
    hasSelection,
    isSelected,
    selectItem,
    deselectItem,
    toggleItem,
    selectAll,
    selectRange,
    clearSelection,
  }
}
