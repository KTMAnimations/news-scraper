'use client';

import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

/**
 * Base Skeleton component with shimmer animation
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'skeleton',
        className
      )}
    />
  );
}

/**
 * Skeleton for EventCard component
 */
export function EventCardSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <div className="p-5 border-b border-border animate-pulse">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Badges */}
          <div className="flex items-center gap-2 mb-2.5">
            <Skeleton className="h-6 w-14" />
            <Skeleton className="h-5 w-24" />
          </div>

          {/* Headline */}
          <Skeleton className={cn('h-5 w-full', compact ? 'max-w-md' : 'max-w-xl')} />
          <Skeleton className="h-5 w-3/4 mt-1.5" />

          {/* Meta info */}
          <div className="flex items-center gap-3 mt-2.5">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>

        {/* Right side - scores */}
        <div className="flex flex-col items-end gap-2.5 shrink-0">
          <Skeleton className="h-7 w-20 rounded-lg" />
          <div className="text-right">
            <Skeleton className="h-8 w-12" />
            <Skeleton className="h-3 w-10 mt-1" />
          </div>
        </div>
      </div>

      {/* Expand indicator */}
      <div className="flex justify-center mt-3">
        <Skeleton className="h-4 w-4 rounded-full" />
      </div>
    </div>
  );
}

/**
 * Skeleton for multiple EventCards (EventFeed)
 */
export function EventFeedSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: count }).map((_, i) => (
        <EventCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for stat cards
 */
export function StatCardSkeleton() {
  return (
    <div className="card p-5 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-8 rounded-lg" />
      </div>
      <Skeleton className="h-9 w-20" />
      <div className="flex items-center gap-2 mt-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-12" />
      </div>
    </div>
  );
}

/**
 * Skeleton for a grid of stat cards
 */
export function StatGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <StatCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for ticker chip
 */
export function TickerChipSkeleton() {
  return <Skeleton className="h-6 w-14 rounded-md" />;
}

/**
 * Skeleton for the filter panel
 */
export function FilterPanelSkeleton() {
  return (
    <div className="card p-4 animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-5 w-16" />
        </div>
        <Skeleton className="h-4 w-4" />
      </div>

      {/* Filter fields */}
      <div className="space-y-5">
        {/* Ticker */}
        <div>
          <Skeleton className="h-3 w-12 mb-2" />
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>

        {/* Event Type */}
        <div>
          <Skeleton className="h-3 w-20 mb-2" />
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>

        {/* Direction */}
        <div>
          <Skeleton className="h-3 w-16 mb-2" />
          <div className="flex gap-2">
            <Skeleton className="h-10 flex-1 rounded-lg" />
            <Skeleton className="h-10 flex-1 rounded-lg" />
            <Skeleton className="h-10 flex-1 rounded-lg" />
          </div>
        </div>

        {/* Sentiment */}
        <div>
          <Skeleton className="h-3 w-16 mb-2" />
          <div className="flex gap-2">
            <Skeleton className="h-8 w-20 rounded-lg" />
            <Skeleton className="h-8 w-20 rounded-lg" />
            <Skeleton className="h-8 w-20 rounded-lg" />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for alert card in list
 */
export function AlertCardSkeleton() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <Skeleton className="h-5 w-5 rounded-full" />
            <Skeleton className="h-5 w-40" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-12" />
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-16" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-8 w-8 rounded-lg" />
          <Skeleton className="h-8 w-8 rounded-lg" />
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for alert list
 */
export function AlertListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <AlertCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for watchlist item
 */
export function WatchlistItemSkeleton() {
  return (
    <div className="flex items-center justify-between p-3 border-b border-border animate-pulse">
      <div className="flex items-center gap-3">
        <Skeleton className="h-6 w-14 rounded-md" />
        <div>
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-20 mt-1" />
        </div>
      </div>
      <Skeleton className="h-8 w-8 rounded-lg" />
    </div>
  );
}

/**
 * Skeleton for watchlist
 */
export function WatchlistSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div>
      {Array.from({ length: count }).map((_, i) => (
        <WatchlistItemSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for chart component
 */
export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div className="card p-4 animate-pulse" style={{ height }}>
      {/* Chart header */}
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-32" />
        <div className="flex gap-2">
          <Skeleton className="h-8 w-16 rounded-lg" />
          <Skeleton className="h-8 w-16 rounded-lg" />
        </div>
      </div>
      {/* Chart area */}
      <div className="relative flex-1 h-full">
        <Skeleton className="h-full w-full rounded-lg" />
      </div>
    </div>
  );
}

/**
 * Skeleton for ticker detail header
 */
export function TickerDetailHeaderSkeleton() {
  return (
    <div className="card p-6 animate-pulse">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Skeleton className="h-10 w-20 rounded-lg" />
            <Skeleton className="h-6 w-48" />
          </div>
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <Skeleton className="h-10 w-24 rounded-lg" />
        </div>
      </div>
      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mt-6 pt-6 border-t border-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="h-3 w-20 mb-2" />
            <Skeleton className="h-7 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for table rows
 */
export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr className="animate-pulse">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-5 w-full max-w-[120px]" />
        </td>
      ))}
    </tr>
  );
}

/**
 * Skeleton for table
 */
export function TableSkeleton({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <table className="w-full">
      <thead>
        <tr>
          {Array.from({ length: columns }).map((_, i) => (
            <th key={i} className="px-4 py-3 text-left">
              <Skeleton className="h-4 w-20" />
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, i) => (
          <TableRowSkeleton key={i} columns={columns} />
        ))}
      </tbody>
    </table>
  );
}

/**
 * Full page loading skeleton
 */
export function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72 mt-2" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-24 rounded-lg" />
          <Skeleton className="h-10 w-24 rounded-lg" />
        </div>
      </div>

      {/* Stats */}
      <StatGridSkeleton />

      {/* Content area */}
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <div className="card">
            <div className="p-4 border-b border-border">
              <Skeleton className="h-6 w-32" />
            </div>
            <EventFeedSkeleton count={5} />
          </div>
        </div>
        <div>
          <FilterPanelSkeleton />
        </div>
      </div>
    </div>
  );
}
