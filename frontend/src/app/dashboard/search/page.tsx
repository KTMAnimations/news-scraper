'use client';

import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, X, Clock, TrendingUp, TrendingDown } from 'lucide-react';
import { api } from '@/lib/api';
import { EventCard } from '@/components/events/EventCard';
import { cn, formatRelativeTime, debounce } from '@/lib/utils';
import type { EventFilters } from '@/types/events';

const RECENT_SEARCHES_KEY = 'micro-alpha-recent-searches';

function getRecentSearches(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const stored = localStorage.getItem(RECENT_SEARCHES_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveRecentSearch(query: string) {
  if (typeof window === 'undefined' || !query.trim()) return;
  try {
    const recent = getRecentSearches();
    const updated = [query, ...recent.filter((q) => q !== query)].slice(0, 5);
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated));
  } catch {
    // Ignore storage errors
  }
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [filters, setFilters] = useState<EventFilters>({});
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  // Load recent searches on mount
  useEffect(() => {
    setRecentSearches(getRecentSearches());
  }, []);

  // Debounced search update
  const debouncedSetQuery = useMemo(
    () =>
      debounce((value: string) => {
        setDebouncedQuery(value);
        if (value.trim()) {
          saveRecentSearch(value.trim());
          setRecentSearches(getRecentSearches());
        }
      }, 300),
    []
  );

  const handleQueryChange = (value: string) => {
    setQuery(value);
    debouncedSetQuery(value);
  };

  const { data, isLoading } = useQuery({
    queryKey: ['search', debouncedQuery, filters],
    queryFn: () => api.search(debouncedQuery, filters),
    enabled: debouncedQuery.length >= 2,
  });

  const events = data?.events || [];
  const total = data?.total || 0;

  const clearSearch = () => {
    setQuery('');
    setDebouncedQuery('');
  };

  const clearRecentSearches = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(RECENT_SEARCHES_KEY);
      setRecentSearches([]);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight">
          Search
        </h1>
        <p className="text-text-secondary">
          Search across all events, tickers, and news
        </p>
      </div>

      {/* Search Input */}
      <div className="card rounded-2xl p-5">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-text-quaternary" />
          <input
            type="text"
            placeholder="Search by ticker, headline, or keyword..."
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            className="input w-full pl-12 pr-12 py-3.5 text-base"
            autoFocus
          />
          {query && (
            <button
              onClick={clearSearch}
              className="absolute right-4 top-1/2 -translate-y-1/2 p-1 hover:bg-hover rounded-lg transition-colors"
            >
              <X className="h-4 w-4 text-text-tertiary" />
            </button>
          )}
        </div>

        {/* Quick Filters */}
        <div className="flex flex-wrap gap-2 mt-4">
          <button
            onClick={() =>
              setFilters((f) => ({
                ...f,
                direction: f.direction === 'BULLISH' ? undefined : 'BULLISH',
              }))
            }
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              filters.direction === 'BULLISH'
                ? 'bg-positive-subtle text-positive'
                : 'bg-bg-tertiary text-text-secondary hover:bg-hover'
            )}
          >
            <TrendingUp className="h-3.5 w-3.5" />
            Bullish Only
          </button>
          <button
            onClick={() =>
              setFilters((f) => ({
                ...f,
                direction: f.direction === 'BEARISH' ? undefined : 'BEARISH',
              }))
            }
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              filters.direction === 'BEARISH'
                ? 'bg-negative-subtle text-negative'
                : 'bg-bg-tertiary text-text-secondary hover:bg-hover'
            )}
          >
            <TrendingDown className="h-3.5 w-3.5" />
            Bearish Only
          </button>
          <button
            onClick={() =>
              setFilters((f) => ({
                ...f,
                min_alpha_score: f.min_alpha_score ? undefined : 0.5,
              }))
            }
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              filters.min_alpha_score
                ? 'bg-accent-subtle text-accent'
                : 'bg-bg-tertiary text-text-secondary hover:bg-hover'
            )}
          >
            <span className="font-mono">α</span>
            High Alpha Only
          </button>
        </div>
      </div>

      {/* Content Area */}
      {!debouncedQuery ? (
        // Recent Searches & Suggestions
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Searches */}
          <div className="card rounded-2xl overflow-hidden">
            <div className="p-5 border-b border-border flex items-center justify-between">
              <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <Clock className="h-4 w-4 text-text-tertiary" />
                Recent Searches
              </h2>
              {recentSearches.length > 0 && (
                <button
                  onClick={clearRecentSearches}
                  className="text-xs text-text-tertiary hover:text-text-secondary"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="p-5">
              {recentSearches.length === 0 ? (
                <p className="text-sm text-text-tertiary text-center py-8">
                  No recent searches
                </p>
              ) : (
                <div className="space-y-2">
                  {recentSearches.map((search) => (
                    <button
                      key={search}
                      onClick={() => handleQueryChange(search)}
                      className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-hover transition-colors text-left"
                    >
                      <Search className="h-4 w-4 text-text-quaternary" />
                      <span className="text-sm text-text-primary">{search}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Popular Searches / Trending */}
          <div className="card rounded-2xl overflow-hidden">
            <div className="p-5 border-b border-border">
              <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-text-tertiary" />
                Suggested Searches
              </h2>
            </div>
            <div className="p-5">
              <div className="flex flex-wrap gap-2">
                {[
                  'FDA approval',
                  'insider buying',
                  'earnings beat',
                  'acquisition',
                  'activist stake',
                  'bankruptcy',
                  'offering',
                  'SEC filing',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => handleQueryChange(suggestion)}
                    className="px-3 py-1.5 rounded-lg text-sm bg-bg-tertiary text-text-secondary hover:bg-hover hover:text-text-primary transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        // Search Results
        <div>
          {/* Results Header */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-text-tertiary">
              {isLoading
                ? 'Searching...'
                : `${total} results for "${debouncedQuery}"`}
            </p>
            {Object.keys(filters).length > 0 && (
              <button
                onClick={() => setFilters({})}
                className="text-sm text-accent hover:text-accent-hover flex items-center gap-1"
              >
                <X className="h-3 w-3" />
                Clear filters
              </button>
            )}
          </div>

          {/* Results */}
          <div className="card rounded-2xl overflow-hidden">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
                <p className="text-sm text-text-tertiary">Searching...</p>
              </div>
            ) : events.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
                  <Search className="h-6 w-6 text-text-quaternary" />
                </div>
                <p className="text-sm font-medium text-text-secondary mb-1">
                  No results found
                </p>
                <p className="text-xs text-text-tertiary">
                  Try a different search term or adjust your filters
                </p>
              </div>
            ) : (
              events.map((event) => <EventCard key={event.id} event={event} />)
            )}
          </div>
        </div>
      )}
    </div>
  );
}
