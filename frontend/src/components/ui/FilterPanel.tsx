'use client';

import { useState, useCallback } from 'react';
import {
  Filter,
  X,
  ChevronDown,
  ChevronUp,
  Search,
  Calendar,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';
import type { EventFilters, SentimentLabel, Direction } from '@/types/events';
import { EVENT_TYPES } from '@/types/events';
import { cn } from '@/lib/utils';

interface FilterPanelProps {
  filters: EventFilters;
  onFiltersChange: (filters: EventFilters) => void;
  onReset: () => void;
  className?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
}

const SENTIMENT_OPTIONS: { value: SentimentLabel; label: string; color: string }[] = [
  { value: 'positive', label: 'Positive', color: 'bg-positive-subtle text-positive' },
  { value: 'neutral', label: 'Neutral', color: 'bg-bg-tertiary text-text-secondary' },
  { value: 'negative', label: 'Negative', color: 'bg-negative-subtle text-negative' },
];

const DIRECTION_OPTIONS: { value: Direction; label: string; icon: typeof TrendingUp }[] = [
  { value: 'BULLISH', label: 'Bullish', icon: TrendingUp },
  { value: 'BEARISH', label: 'Bearish', icon: TrendingDown },
  { value: 'NEUTRAL', label: 'Neutral', icon: Minus },
];

export function FilterPanel({
  filters,
  onFiltersChange,
  onReset,
  className,
  collapsible = true,
  defaultExpanded = true,
}: FilterPanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const updateFilter = useCallback(
    <K extends keyof EventFilters>(key: K, value: EventFilters[K]) => {
      onFiltersChange({ ...filters, [key]: value });
    },
    [filters, onFiltersChange]
  );

  const activeFilterCount = Object.values(filters).filter(
    (v) => v !== undefined && v !== null && v !== ''
  ).length;

  const formatEventType = (type: string) => {
    return type
      .split('_')
      .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
      .join(' ');
  };

  return (
    <div className={cn('card', className)}>
      {/* Header */}
      <div
        className={cn(
          'flex items-center justify-between p-4',
          collapsible && 'cursor-pointer hover:bg-hover transition-colors rounded-t-xl'
        )}
        onClick={() => collapsible && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-text-secondary" />
          <span className="font-medium text-text-primary">Filters</span>
          {activeFilterCount > 0 && (
            <span className="badge badge-accent text-xs">{activeFilterCount} active</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeFilterCount > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onReset();
              }}
              className="btn btn-ghost text-xs text-text-tertiary hover:text-negative"
            >
              <X className="h-3.5 w-3.5" />
              Clear
            </button>
          )}
          {collapsible && (
            <div className="text-text-tertiary">
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Filter Content */}
      {isExpanded && (
        <div className="p-4 pt-0 space-y-5 animate-fade-in">
          {/* Ticker Search */}
          <div>
            <label className="data-label block mb-2">Ticker</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-quaternary" />
              <input
                type="text"
                placeholder="Search ticker..."
                value={filters.ticker || ''}
                onChange={(e) => updateFilter('ticker', e.target.value.toUpperCase() || undefined)}
                className="input pl-10"
              />
            </div>
          </div>

          {/* Event Type */}
          <div>
            <label className="data-label block mb-2">Event Type</label>
            <select
              value={filters.event_type || ''}
              onChange={(e) => updateFilter('event_type', e.target.value || undefined)}
              className="input"
            >
              <option value="">All Types</option>
              {EVENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {formatEventType(type)}
                </option>
              ))}
            </select>
          </div>

          {/* Direction */}
          <div>
            <label className="data-label block mb-2">Direction</label>
            <div className="flex gap-2">
              {DIRECTION_OPTIONS.map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  onClick={() =>
                    updateFilter('direction', filters.direction === value ? undefined : value)
                  }
                  className={cn(
                    'flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border transition-all text-sm font-medium',
                    filters.direction === value
                      ? value === 'BULLISH'
                        ? 'bg-positive-subtle border-positive text-positive'
                        : value === 'BEARISH'
                        ? 'bg-negative-subtle border-negative text-negative'
                        : 'bg-bg-tertiary border-border-strong text-text-secondary'
                      : 'bg-bg-elevated border-border hover:border-border-strong text-text-secondary hover:text-text-primary'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Sentiment */}
          <div>
            <label className="data-label block mb-2">Sentiment</label>
            <div className="flex flex-wrap gap-2">
              {SENTIMENT_OPTIONS.map(({ value, label, color }) => (
                <button
                  key={value}
                  onClick={() =>
                    updateFilter(
                      'sentiment_label',
                      filters.sentiment_label === value ? undefined : value
                    )
                  }
                  className={cn(
                    'px-3 py-1.5 rounded-lg border text-sm font-medium transition-all',
                    filters.sentiment_label === value
                      ? cn(color, 'border-transparent')
                      : 'bg-bg-elevated border-border hover:border-border-strong text-text-secondary hover:text-text-primary'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Min Alpha Score */}
          <div>
            <label className="data-label block mb-2">
              Min Alpha Score: {filters.min_alpha_score !== undefined ? `${(filters.min_alpha_score * 100).toFixed(0)}%` : 'Any'}
            </label>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={filters.min_alpha_score !== undefined ? filters.min_alpha_score * 100 : 0}
              onChange={(e) => {
                const value = parseInt(e.target.value);
                updateFilter('min_alpha_score', value > 0 ? value / 100 : undefined);
              }}
              className="w-full h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none
                [&::-webkit-slider-thumb]:w-4
                [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full
                [&::-webkit-slider-thumb]:bg-accent
                [&::-webkit-slider-thumb]:cursor-pointer
                [&::-webkit-slider-thumb]:shadow-md
                [&::-webkit-slider-thumb]:hover:bg-accent-hover
                [&::-moz-range-thumb]:w-4
                [&::-moz-range-thumb]:h-4
                [&::-moz-range-thumb]:rounded-full
                [&::-moz-range-thumb]:bg-accent
                [&::-moz-range-thumb]:cursor-pointer
                [&::-moz-range-thumb]:border-0"
            />
            <div className="flex justify-between text-xs text-text-quaternary mt-1">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="data-label block mb-2">
                <Calendar className="inline h-3 w-3 mr-1" />
                Start Date
              </label>
              <input
                type="date"
                value={filters.start_date || ''}
                onChange={(e) => updateFilter('start_date', e.target.value || undefined)}
                className="input"
              />
            </div>
            <div>
              <label className="data-label block mb-2">
                <Calendar className="inline h-3 w-3 mr-1" />
                End Date
              </label>
              <input
                type="date"
                value={filters.end_date || ''}
                onChange={(e) => updateFilter('end_date', e.target.value || undefined)}
                className="input"
              />
            </div>
          </div>

          {/* Source Name */}
          <div>
            <label className="data-label block mb-2">Source</label>
            <input
              type="text"
              placeholder="Filter by source..."
              value={filters.source_name || ''}
              onChange={(e) => updateFilter('source_name', e.target.value || undefined)}
              className="input"
            />
          </div>
        </div>
      )}
    </div>
  );
}
