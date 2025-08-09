import { Grid2X2, List, ArrowUpDown, Star, LayoutGrid, CheckSquare } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { Badge } from "@/components/ui/badge"
import type { ViewMode, SortBy } from "@/app/timelapses/page"

interface LibraryHeaderProps {
  viewMode: ViewMode
  sortBy: SortBy
  sortOrder: "asc" | "desc"
  starredOnly: boolean
  onViewModeChange: (mode: ViewMode) => void
  onSortChange: (sort: SortBy, order: "asc" | "desc") => void
  onStarredFilter: (starred: boolean) => void
  hasSelection: boolean
  selectedCount: number
  onSelectAll: () => void
  onClearSelection: () => void
}

export function LibraryHeader({
  viewMode,
  sortBy,
  sortOrder,
  starredOnly,
  onViewModeChange,
  onSortChange,
  onStarredFilter,
  hasSelection,
  selectedCount,
  onSelectAll,
  onClearSelection,
}: LibraryHeaderProps) {
  const handleSortChange = (value: string) => {
    const [newSortBy, newOrder] = value.split("-") as [SortBy, "asc" | "desc"]
    onSortChange(newSortBy, newOrder)
  }

  return (
    <div className="sticky top-0 z-10 glass-strong border border-purple-muted/30 rounded-2xl p-4 space-y-4 backdrop-blur-xl">
      {/* Main Controls Row */}
      <div className="flex items-center justify-between">
        {/* Left Side - View Mode & Sorting */}
        <div className="flex items-center space-x-4">
          {/* View Mode Toggle */}
          <div className="flex items-center bg-black/30 rounded-lg p-1 border border-purple-muted/30">
            <Button
              variant={viewMode === "card" ? "default" : "ghost"}
              size="sm"
              onClick={() => onViewModeChange("card")}
              className={`px-3 py-2 ${
                viewMode === "card" 
                  ? "bg-gradient-to-r from-pink/80 to-cyan/80 text-black" 
                  : "text-white hover:bg-purple/20"
              }`}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === "row" ? "default" : "ghost"}
              size="sm"
              onClick={() => onViewModeChange("row")}
              className={`px-3 py-2 ${
                viewMode === "row" 
                  ? "bg-gradient-to-r from-pink/80 to-cyan/80 text-black" 
                  : "text-white hover:bg-purple/20"
              }`}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>

          {/* Sort Controls */}
          <div className="relative">
            <Select value={`${sortBy}-${sortOrder}`} onValueChange={handleSortChange}>
              <SelectTrigger className="w-[200px] bg-black/30 border-purple-muted/30 text-white">
                <ArrowUpDown className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Sort by..." />
              </SelectTrigger>
              <SelectContent className="bg-black/90 border-purple-muted/30 text-white">
                <SelectItem value="camera-asc" className="focus:bg-purple/20">
                  Camera (A → Z)
                </SelectItem>
                <SelectItem value="camera-desc" className="focus:bg-purple/20">
                  Camera (Z → A)
                </SelectItem>
                <SelectItem value="alphabetical-asc" className="focus:bg-purple/20">
                  Name (A → Z)
                </SelectItem>
                <SelectItem value="alphabetical-desc" className="focus:bg-purple/20">
                  Name (Z → A)
                </SelectItem>
                <SelectItem value="chronological-desc" className="focus:bg-purple/20">
                  Newest First
                </SelectItem>
                <SelectItem value="chronological-asc" className="focus:bg-purple/20">
                  Oldest First
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Starred Filter */}
          <Button
            variant={starredOnly ? "default" : "outline"}
            size="sm"
            onClick={() => onStarredFilter(!starredOnly)}
            className={`flex items-center space-x-2 ${
              starredOnly 
                ? "bg-gradient-to-r from-yellow/80 to-yellow/60 text-black border-yellow/40" 
                : "bg-black/30 border-purple-muted/30 text-white hover:bg-purple/20"
            }`}
          >
            <Star className={`h-4 w-4 ${starredOnly ? "fill-current" : ""}`} />
            <span>Starred</span>
            {starredOnly && (
              <Badge className="bg-yellow/20 text-yellow-400 text-xs">
                ON
              </Badge>
            )}
          </Button>
        </div>

        {/* Right Side - Selection Controls */}
        {hasSelection ? (
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <CheckSquare className="h-4 w-4 text-cyan" />
              <span className="text-sm text-white font-medium">
                {selectedCount} selected
              </span>
            </div>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={onClearSelection}
              className="bg-black/30 border-purple-muted/30 text-white hover:bg-purple/20"
            >
              Clear
            </Button>
          </div>
        ) : (
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onSelectAll}
            className="text-grey-light/70 hover:text-white hover:bg-purple/20"
          >
            Select All
          </Button>
        )}
      </div>

      {/* Multiselect Hint */}
      {viewMode === "card" && !hasSelection && (
        <div className="flex items-center text-xs text-grey-light/60">
          <div className="w-2 h-2 rounded-full bg-cyan/40 mr-2" />
          Hover over cards to see selection checkboxes
        </div>
      )}
    </div>
  )
}
