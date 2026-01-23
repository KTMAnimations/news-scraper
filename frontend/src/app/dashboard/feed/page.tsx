'use client';

import { useState, useCallback, useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import {
  Filter,
  SortAsc,
  SortDesc,
  RefreshCw,
  X,
} from 'lucide-react';
import { api } from '@/lib/api';
import { EventCard } from '@/components/events/EventCard';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { WatchlistFilterToggle } from '@/components/watchlist/WatchlistQuickView';
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll';
import { useWatchlist } from '@/hooks/useWatchlist';
import { cn } from '@/lib/utils';
import type { EventFilters, Direction, SentimentLabel, Event } from '@/types/events';

const EVENT_TYPES = [
  'INSIDER_BUY',
  'INSIDER_SELL',
  'EARNINGS_BEAT',
  'EARNINGS_MISS',
  'FDA_APPROVAL',
  'FDA_REJECTION',
  'ACQUISITION',
  'BANKRUPTCY',
  'ACTIVIST_STAKE',
  'OFFERING',
  'MANAGEMENT_CHANGE',
  'REGULATORY_ACTION',
  'SEC_FILING',
  'NEWS',
  'SOCIAL_MENTION',
];

const DIRECTIONS: Direction[] = ['BULLISH', 'BEARISH', 'NEUTRAL'];
const SENTIMENTS: SentimentLabel[] = ['positive', 'negative', 'neutral'];

type SortField = 'event_time' | 'alpha_score' | 'sentiment_score';
type SortOrder = 'asc' | 'desc';

const PAGE_SIZE = 20;

export default function EventFeedPage() {
  const [filters, setFilters] = useState<EventFilters>({});
  const [sortField, setSortField] = useState<SortField>('event_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [showFilters, setShowFilters] = useState(false);
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const { items: watchlistItems } = useWatchlist();

  // Use infinite query for pagination
  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
    isFetching,
  } = useInfiniteQuery({
    queryKey: ['events', 'feed', filters],
    queryFn: async ({ pageParam = 1 }) => {
      return api.getEvents({
        ...filters,
        page: pageParam,
        page_size: PAGE_SIZE,
      });
    },
    getNextPageParam: (lastPage, allPages) => {
      const totalLoaded = allPages.length * PAGE_SIZE;
      if (totalLoaded < lastPage.total) {
        return allPages.length + 1;
      }
      return undefined;
    },
    initialPageParam: 1,
  });

  // Flatten all pages into a single array of events
  const allEvents = useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap((page) => page.events);
  }, [data?.pages]);

  const total = data?.pages[0]?.total || 0;

  // Filter for watchlist only if enabled
  const filteredEvents = useMemo(() => {
    if (!watchlistOnly || watchlistItems.length === 0) return allEvents;
    const watchedTickers = new Set(watchlistItems.map((item) => item.ticker));
    return allEvents.filter((event: Event) => watchedTickers.has(event.ticker));
  }, [allEvents, watchlistOnly, watchlistItems]);

  // Sort events locally (API should handle this, but as fallback)
  const sortedEvents = useMemo(() => {
    return [...filteredEvents].sort((a: Event, b: Event) => {
      let aVal: number, bVal: number;
      switch (sortField) {
        case 'alpha_score':
          aVal = a.alpha_score || 0;
          bVal = b.alpha_score || 0;
          break;
        case 'sentiment_score':
          aVal = a.sentiment_score || 0;
          bVal = b.sentiment_score || 0;
          break;
        default:
          aVal = new Date(a.event_time).getTime();
          bVal = new Date(b.event_time).getTime();
      }
      return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
    });
  }, [filteredEvents, sortField, sortOrder]);

  // Infinite scroll hook
  const { sentinelRef } = useInfiniteScroll({
    onLoadMore: () => {
      if (hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    hasMore: !!hasNextPage,
    isLoading: isFetchingNextPage,
    rootMargin: '200px',
  });

  const updateFilter = useCallback(
    (key: keyof EventFilters, value: string | number | undefined) => {
      setFilters((prev) => {
        if (value === undefined || value === '') {
          const { [key]: _, ...rest } = prev;
          return rest;
        }
        return { ...prev, [key]: value };
      });
    },
    []
  );

  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const activeFilterCount = Object.keys(filters).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight">
            Event Feed
          </h1>
          <p className="text-text-secondary">
            Browse and filter all market events
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn btn-secondary flex items-center gap-2"
          >
            <RefreshCw
              className={cn('h-4 w-4', isFetching && 'animate-spin')}
            />
            Refresh
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'btn flex items-center gap-2',
              showFilters ? 'btn-primary' : 'btn-secondary'
            )}
          >
            <Filter className="h-4 w-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs bg-accent text-bg-primary rounded-full">
                {activeFilterCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="card rounded-2xl p-5 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-text-primary">Filters</h3>
            {activeFilterCount > 0 && (
              <button
                onClick={clearFilters}
                className="text-sm text-accent hover:text-accent-hover flex items-center gap-1"
              >
                <X className="h-3 w-3" />
                Clear all
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Ticker Filter */}
            <div>
              <label className="data-label mb-2 block">Ticker</label>
              <input
                type="text"
                placeholder="e.g., AAPL"
                value={filters.ticker || ''}
                onChange={(e) =>
                  updateFilter('ticker', e.target.value.toUpperCase())
                }
                className="input w-full"
              />
            </div>

            {/* Event Type Filter */}
            <div>
              <label className="data-label mb-2 block">Event Type</label>
              <select
                value={filters.event_type || ''}
                onChange={(e) => updateFilter('event_type', e.target.value)}
                className="input w-full"
              >
                <option value="">All Types</option>
                {EVENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>

            {/* Direction Filter */}
            <div>
              <label className="data-label mb-2 block">Direction</label>
              <select
                value={filters.direction || ''}
                onChange={(e) =>
                  updateFilter('direction', e.target.value as Direction)
                }
                className="input w-full"
              >
                <option value="">All Directions</option>
                {DIRECTIONS.map((dir) => (
                  <option key={dir} value={dir}>
                    {dir}
                  </option>
                ))}
              </select>
            </div>

            {/* Sentiment Filter */}
            <div>
              <label className="data-label mb-2 block">Sentiment</label>
              <select
                value={filters.sentiment_label || ''}
                onChange={(e) =>
                  updateFilter(
                    'sentiment_label',
                    e.target.value as SentimentLabel
                  )
                }
                className="input w-full"
              >
                <option value="">All Sentiments</option>
                {SENTIMENTS.map((sent) => (
                  <option key={sent} value={sent}>
                    {sent.charAt(0).toUpperCase() + sent.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Min Alpha Filter */}
            <div>
              <label className="data-label mb-2 block">Min Alpha Score</label>
              <input
                type="number"
                min="0"
                max="100"
                step="10"
                placeholder="e.g., 50"
                value={
                  filters.min_alpha_score
                    ? filters.min_alpha_score * 100
                    : ''
                }
                onChange={(e) =>
                  updateFilter(
                    'min_alpha_score',
                    e.target.value ? Number(e.target.value) / 100 : undefined
                  )
                }
                className="input w-full"
              />
            </div>

            {/* Source Filter */}
            <div>
              <label className="data-label mb-2 block">Source</label>
              <input
                type="text"
                placeholder="e.g., SEC EDGAR"
                value={filters.source_name || ''}
                onChange={(e) => updateFilter('source_name', e.target.value)}
                className="input w-full"
              />
            </div>

            {/* Date Range */}
            <div>
              <label className="data-label mb-2 block">Start Date</label>
              <input
                type="date"
                value={filters.start_date || ''}
                onChange={(e) => updateFilter('start_date', e.target.value)}
                className="input w-full"
              />
            </div>

            <div>
              <label className="data-label mb-2 block">End Date</label>
              <input
                type="date"
                value={filters.end_date || ''}
                onChange={(e) => updateFilter('end_date', e.target.value)}
                className="input w-full"
              />
            </div>
          </div>
        </div>
      )}

      {/* Sort Controls & Results Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <p className="text-sm text-text-tertiary">
            Showing {sortedEvents.length} of {total} events
          </p>
          <WatchlistFilterToggle
            enabled={watchlistOnly}
            onChange={setWatchlistOnly}
          />
        </div>

        <div className="flex items-center gap-3">
          <span className="text-sm text-text-tertiary">Sort by:</span>
          <select
            value={sortField}
            onChange={(e) => setSortField(e.target.value as SortField)}
            className="input py-1.5 text-sm"
          >
            <option value="event_time">Time</option>
            <option value="alpha_score">Alpha Score</option>
            <option value="sentiment_score">Sentiment</option>
          </select>
          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="p-2 hover:bg-hover rounded-lg transition-colors"
            title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
          >
            {sortOrder === 'asc' ? (
              <SortAsc className="h-4 w-4 text-text-secondary" />
            ) : (
              <SortDesc className="h-4 w-4 text-text-secondary" />
            )}
          </button>
        </div>
      </div>

      {/* Events List */}
      <div className="card rounded-2xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <LoadingSpinner message="Loading events..." />
          </div>
        ) : sortedEvents.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
              <span className="text-2xl">🔍</span>
            </div>
            <p className="text-sm font-medium text-text-secondary mb-1">
              No events found
            </p>
            <p className="text-xs text-text-tertiary">
              Try adjusting your filters
            </p>
          </div>
        ) : (
          <>
            {sortedEvents.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}

            {/* Infinite scroll sentinel */}
            <div
              ref={sentinelRef}
              className="py-4"
            >
              {isFetchingNextPage && (
                <LoadingSpinner size="sm" message="Loading more events..." />
              )}
              {!hasNextPage && sortedEvents.length > 0 && (
                <p className="text-center text-sm text-text-tertiary py-4">
                  You've reached the end of the feed
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
