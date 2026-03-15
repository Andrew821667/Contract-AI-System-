'use client'

interface SkeletonProps {
  className?: string
}

/** Animated skeleton placeholder for loading states */
export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div className={`animate-pulse bg-gray-200 rounded-xl ${className}`} />
  )
}

/** Card-shaped skeleton with title and lines */
export function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-8 rounded-lg" />
      </div>
      <Skeleton className="h-8 w-24" />
      <Skeleton className="h-3 w-full" />
    </div>
  )
}

/** Row-shaped skeleton for list items */
export function SkeletonRow() {
  return (
    <div className="flex items-center space-x-4 p-5 bg-white rounded-xl border border-gray-100">
      <Skeleton className="w-12 h-12 rounded-xl" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-3 w-32" />
      </div>
      <Skeleton className="h-8 w-20 rounded-full" />
    </div>
  )
}

/** Chart-area skeleton */
export function SkeletonChart() {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
      <Skeleton className="h-5 w-40 mb-4" />
      <Skeleton className="h-[300px] w-full" />
    </div>
  )
}
