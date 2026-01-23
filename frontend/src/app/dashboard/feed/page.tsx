'use client';

import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Filter,
  SortAsc,
  SortDesc,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react';
import { api } from '@/lib/api';
import { EventCard } from '@/components/events/EventCard';
import { cn } from '@/lib/utils';
import type { EventFilters, Direction, SentimentLabel } from '@/types/events';

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

export default function EventFeedPage() {
  const [filters, setFilters] = useState<EventFilters>({});
  const [sortField, setSortField] = useState<SortField>('event_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [page, setPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);
  const pageSize = 20;

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['events', 'feed', filters, page, pageSize],
    queryFn: () =>
      api.getEvents({
        ...filters,
        page,
        page_size: pageSize,
      }),
  });

  const events = data?.events || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  // Sort events locally (API should handle this, but as fallback)
  const sortedEvents = [...events].sort((a, b) => {
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

  const updateFilter = useCallback(
    (key: keyof EventFilters, value: string | number | undefined) => {
      setFilters((prev) => {
        if (value === undefined || value === '') {
          const { [key]: _, ...rest } = prev;
          return rest;
        }
        return { ...prev, [key]: value };
      });
      setPage(1);
    },
    []
  );

  const clearFilters = useCallback(() => {
    setFilters({});
    setPage(1);
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
        <p className="text-sm text-text-tertiary">
          Showing {events.length} of {total} events
        </p>

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
            <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
            <p className="text-sm text-text-tertiary">Loading events...</p>
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
          sortedEvents.map((event) => (
            <EventCard key={event.id} event={event} />
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn btn-secondary p-2 disabled:opacity-50"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (page <= 3) {
                pageNum = i + 1;
              } else if (page >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = page - 2 + i;
              }

              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={cn(
                    'w-9 h-9 rounded-lg text-sm font-medium transition-colors',
                    page === pageNum
                      ? 'bg-text-primary text-bg-primary'
                      : 'hover:bg-hover text-text-secondary'
                  )}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn btn-secondary p-2 disabled:opacity-50"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
