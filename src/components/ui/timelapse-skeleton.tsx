// src/components/ui/timelapse-skeleton.tsx
import { Skeleton } from "./skeleton"
import { Card, CardContent, CardHeader } from "./card"

interface TimelapseSectionSkeletonProps {
  count?: number
}

export function TimelapseSectionSkeleton({ count = 5 }: TimelapseSectionSkeletonProps) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }, (_, i) => (
        <Card key={i} className="w-full">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <Skeleton className="h-4 w-[200px]" />
              <Skeleton className="h-3 w-[150px]" />
            </div>
            <Skeleton className="h-6 w-[80px]" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-4">
              <Skeleton className="h-12 w-12 rounded" />
              <div className="space-y-2">
                <Skeleton className="h-3 w-[100px]" />
                <Skeleton className="h-3 w-[80px]" />
              </div>
              <div className="ml-auto space-y-2">
                <Skeleton className="h-3 w-[60px]" />
                <Skeleton className="h-3 w-[40px]" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

interface TimelapseSectionErrorProps {
  error: string
  onRetry: () => void
}

export function TimelapseSectionError({ error, onRetry }: TimelapseSectionErrorProps) {
  return (
    <Card className="w-full border-destructive">
      <CardContent className="flex flex-col items-center justify-center py-8">
        <div className="text-center space-y-2">
          <p className="text-sm text-destructive">Failed to load timelapses</p>
          <p className="text-xs text-muted-foreground">{error}</p>
          <button
            onClick={onRetry}
            className="text-xs text-primary hover:underline"
          >
            Try again
          </button>
        </div>
      </CardContent>
    </Card>
  )
}