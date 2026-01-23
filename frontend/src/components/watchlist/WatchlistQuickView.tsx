'use client';

import Link from 'next/link';
import { Star, ChevronRight, Plus, TrendingUp, TrendingDown } from 'lucide-react';
import { useWatchlist } from '@/hooks/useWatchlist';
import { cn } from '@/lib/utils';

interface WatchlistQuickViewProps {
  maxItems?: number;
  compact?: boolean;
}

export function WatchlistQuickView({ maxItems = 5, compact = false }: WatchlistQuickViewProps) {
  const { items, isLoading } = useWatchlist();
  const displayItems = items.slice(0, maxItems);
  const hasMore = items.length > maxItems;

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-8 skeleton rounded-lg" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className={cn('text-center', compact ? 'py-3' : 'py-4')}>
        <div className={cn(
          'rounded-lg bg-warning-subtle mx-auto mb-2 flex items-center justify-center',
          compact ? 'w-8 h-8' : 'w-10 h-10'
        )}>
          <Star className={cn(compact ? 'h-4 w-4' : 'h-5 w-5', 'text-warning')} />
        </div>
        <p className={cn('text-text-tertiary mb-2', compact ? 'text-2xs' : 'text-xs')}>
          No tickers watched
        </p>
        <Link
          href="/dashboard/watchlist"
          className={cn(
            'inline-flex items-center gap-1 text-accent hover:text-accent-hover transition-colors',
            compact ? 'text-2xs' : 'text-xs'
          )}
        >
          <Plus className="h-3 w-3" />
          Add tickers
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {displayItems.map((item) => (
        <Link
          key={item.ticker}
          href={`/dashboard/ticker/${item.ticker}`}
          className={cn(
            'flex items-center justify-between rounded-lg hover:bg-hover transition-colors group',
            compact ? 'px-2 py-1.5' : 'px-3 py-2'
          )}
        >
          <div className="flex items-center gap-2">
            <Star className={cn(
              'text-warning fill-current',
              compact ? 'h-3 w-3' : 'h-3.5 w-3.5'
            )} />
            <span className={cn(
              'ticker-chip group-hover:bg-accent group-hover:text-bg-primary transition-colors',
              compact ? 'text-2xs px-1.5 py-0.5' : 'text-xs'
            )}>
              {item.ticker}
            </span>
          </div>
          <ChevronRight className={cn(
            'text-text-quaternary group-hover:text-text-secondary transition-colors',
            compact ? 'h-3 w-3' : 'h-4 w-4'
          )} />
        </Link>
      ))}

      {hasMore && (
        <Link
          href="/dashboard/watchlist"
          className={cn(
            'flex items-center justify-center gap-1 text-accent hover:text-accent-hover transition-colors mt-2',
            compact ? 'text-2xs py-1' : 'text-xs py-2'
          )}
        >
          View all {items.length} tickers
          <ChevronRight className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

// Watchlist filter toggle for use in event feeds
interface WatchlistFilterToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  className?: string;
}

export function WatchlistFilterToggle({ enabled, onChange, className }: WatchlistFilterToggleProps) {
  const { items } = useWatchlist();

  return (
    <button
      onClick={() => onChange(!enabled)}
      disabled={items.length === 0}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-lg transition-colors text-sm font-medium',
        enabled
          ? 'bg-warning-subtle text-warning'
          : 'bg-bg-tertiary text-text-secondary hover:bg-hover',
        items.length === 0 && 'opacity-50 cursor-not-allowed',
        className
      )}
      title={
        items.length === 0
          ? 'Add tickers to watchlist first'
          : enabled
          ? 'Showing watchlist only'
          : 'Show all events'
      }
    >
      <Star className={cn('h-4 w-4', enabled && 'fill-current')} />
      {enabled ? 'Watchlist Only' : 'All Tickers'}
      {items.length > 0 && (
        <span className={cn(
          'px-1.5 py-0.5 text-xs rounded-full',
          enabled ? 'bg-warning/20 text-warning' : 'bg-bg-secondary text-text-tertiary'
        )}>
          {items.length}
        </span>
      )}
    </button>
  );
}
