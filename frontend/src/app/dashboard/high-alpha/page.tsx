'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Clock,
  ExternalLink,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { cn, formatRelativeTime, formatDateTime } from '@/lib/utils';
import { SentimentBadge } from '@/components/events/SentimentBadge';
import type { Event } from '@/types/events';

export default function HighAlphaPage() {
  const [minScore, setMinScore] = useState(50);
  const [timeRange, setTimeRange] = useState(24);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);

  const { data: events = [], isLoading, refetch, isFetching } = useQuery({
    queryKey: ['events', 'high-alpha', minScore, timeRange],
    queryFn: () => api.getHighAlphaEvents(minScore / 100, 50),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Filter by time range
  const filteredEvents = events.filter((event) => {
    const eventTime = new Date(event.event_time).getTime();
    const cutoff = Date.now() - timeRange * 60 * 60 * 1000;
    return eventTime >= cutoff;
  });

  // Separate bullish and bearish
  const bullishEvents = filteredEvents.filter((e) => e.direction === 'BULLISH');
  const bearishEvents = filteredEvents.filter((e) => e.direction === 'BEARISH');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight flex items-center gap-3">
            <span className="w-10 h-10 rounded-xl bg-accent-subtle flex items-center justify-center">
              <Zap className="h-5 w-5 text-accent" />
            </span>
            High Alpha Signals
          </h1>
          <p className="text-text-secondary">
            Top-scoring events with significant market impact potential
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Controls */}
      <div className="card rounded-2xl p-5">
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-3">
            <span className="text-sm text-text-secondary">Min Alpha:</span>
            <div className="flex items-center gap-2">
              {[50, 60, 70, 80, 90].map((score) => (
                <button
                  key={score}
                  onClick={() => setMinScore(score)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                    minScore === score
                      ? 'bg-accent text-bg-primary'
                      : 'bg-bg-tertiary text-text-secondary hover:bg-hover'
                  )}
                >
                  {score}+
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-sm text-text-secondary">Time Range:</span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(Number(e.target.value))}
              className="input py-1.5 text-sm"
            >
              <option value={1}>Last hour</option>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={48}>Last 48 hours</option>
              <option value={168}>Last week</option>
            </select>
          </div>

          <div className="ml-auto text-sm text-text-tertiary">
            {filteredEvents.length} signals found
          </div>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card-interactive rounded-2xl p-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-accent-subtle flex items-center justify-center">
              <span className="font-mono text-xl font-bold text-accent">α</span>
            </div>
            <div>
              <p className="data-label mb-1">Total Signals</p>
              <p className="font-mono text-3xl font-bold text-text-primary">
                {filteredEvents.length}
              </p>
            </div>
          </div>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-positive-subtle flex items-center justify-center">
              <TrendingUp className="h-6 w-6 text-positive" />
            </div>
            <div>
              <p className="data-label mb-1">Bullish</p>
              <p className="font-mono text-3xl font-bold text-positive">
                {bullishEvents.length}
              </p>
            </div>
          </div>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-negative-subtle flex items-center justify-center">
              <TrendingDown className="h-6 w-6 text-negative" />
            </div>
            <div>
              <p className="data-label mb-1">Bearish</p>
              <p className="font-mono text-3xl font-bold text-negative">
                {bearishEvents.length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signals List */}
        <div className="card rounded-2xl overflow-hidden">
          <div className="p-5 border-b border-border bg-gradient-to-r from-accent/10 to-transparent">
            <h2 className="text-lg font-semibold text-text-primary">
              All High Alpha Signals
            </h2>
          </div>
          <div className="max-h-[600px] overflow-y-auto custom-scrollbar">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
                <p className="text-sm text-text-tertiary">Loading signals...</p>
              </div>
            ) : filteredEvents.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-accent-subtle mx-auto mb-4 flex items-center justify-center">
                  <span className="font-mono text-2xl font-bold text-accent">
                    α
                  </span>
                </div>
                <p className="text-sm font-medium text-text-secondary mb-1">
                  No high-alpha signals
                </p>
                <p className="text-xs text-text-tertiary">
                  Try lowering the minimum score or expanding the time range
                </p>
              </div>
            ) : (
              filteredEvents.map((event) => (
                <div
                  key={event.id}
                  onClick={() => setSelectedEvent(event)}
                  className={cn(
                    'p-5 hover:bg-hover transition-colors cursor-pointer border-b border-border last:border-0',
                    selectedEvent?.id === event.id && 'bg-bg-secondary'
                  )}
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/dashboard/ticker/${event.ticker}`}
                        onClick={(e) => e.stopPropagation()}
                        className="ticker-chip hover:bg-accent hover:text-bg-primary transition-colors"
                      >
                        {event.ticker}
                      </Link>
                      <span
                        className={cn(
                          'flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-lg',
                          event.direction === 'BULLISH'
                            ? 'bg-positive-subtle text-positive'
                            : event.direction === 'BEARISH'
                            ? 'bg-negative-subtle text-negative'
                            : 'bg-bg-tertiary text-text-tertiary'
                        )}
                      >
                        {event.direction === 'BULLISH' ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {event.direction}
                      </span>
                    </div>
                    <span className="text-xs text-text-tertiary flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatRelativeTime(event.event_time)}
                    </span>
                  </div>
                  <p className="text-sm text-text-primary font-medium line-clamp-2 leading-snug mb-3">
                    {event.headline}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="badge badge-neutral text-xs">
                      {event.event_type.replace(/_/g, ' ')}
                    </span>
                    <div className="text-right">
                      <span
                        className={cn(
                          'font-mono text-xl font-bold',
                          (event.alpha_score || 0) >= 0.8
                            ? 'text-accent'
                            : 'text-text-primary'
                        )}
                      >
                        {((event.alpha_score || 0) * 100).toFixed(0)}
                      </span>
                      <span className="data-label ml-1.5">alpha</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Selected Event Detail */}
        <div className="card rounded-2xl overflow-hidden">
          <div className="p-5 border-b border-border">
            <h2 className="text-lg font-semibold text-text-primary">
              Signal Details
            </h2>
          </div>
          {selectedEvent ? (
            <div className="p-5 space-y-5">
              {/* Header */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Link
                    href={`/dashboard/ticker/${selectedEvent.ticker}`}
                    className="ticker-chip text-lg px-3 py-1.5 hover:bg-accent hover:text-bg-primary transition-colors"
                  >
                    {selectedEvent.ticker}
                  </Link>
                  <span
                    className={cn(
                      'flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg',
                      selectedEvent.direction === 'BULLISH'
                        ? 'bg-positive-subtle text-positive'
                        : selectedEvent.direction === 'BEARISH'
                        ? 'bg-negative-subtle text-negative'
                        : 'bg-bg-tertiary text-text-tertiary'
                    )}
                  >
                    {selectedEvent.direction === 'BULLISH' ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    {selectedEvent.direction}
                  </span>
                </div>
                <h3 className="text-lg font-medium text-text-primary leading-snug">
                  {selectedEvent.headline}
                </h3>
              </div>

              {/* Alpha Score Display */}
              <div className="card rounded-xl p-5 bg-gradient-to-br from-accent/10 to-transparent border-accent/20">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="data-label mb-1">Alpha Score</p>
                    <p className="font-mono text-4xl font-bold text-accent">
                      {((selectedEvent.alpha_score || 0) * 100).toFixed(0)}
                    </p>
                  </div>
                  <div className="w-16 h-16 rounded-2xl bg-accent/20 flex items-center justify-center">
                    <span className="font-mono text-3xl font-bold text-accent">
                      α
                    </span>
                  </div>
                </div>
              </div>

              {/* Summary */}
              {selectedEvent.summary && (
                <div>
                  <p className="data-label mb-2">Summary</p>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {selectedEvent.summary}
                  </p>
                </div>
              )}

              {/* Details Grid */}
              <div className="grid grid-cols-2 gap-4">
                {selectedEvent.sentiment_label && (
                  <div>
                    <p className="data-label mb-2">Sentiment</p>
                    <SentimentBadge
                      sentiment={selectedEvent.sentiment_label}
                      confidence={selectedEvent.sentiment_confidence}
                    />
                  </div>
                )}

                <div>
                  <p className="data-label mb-2">Event Type</p>
                  <span className="badge badge-neutral">
                    {selectedEvent.event_type.replace(/_/g, ' ')}
                  </span>
                </div>

                <div>
                  <p className="data-label mb-2">Event Time</p>
                  <p className="text-sm text-text-primary">
                    {formatDateTime(selectedEvent.event_time)}
                  </p>
                </div>

                <div>
                  <p className="data-label mb-2">Source</p>
                  <p className="text-sm text-text-primary">
                    {selectedEvent.source_name || 'Unknown'}
                  </p>
                </div>
              </div>

              {/* Related Tickers */}
              {selectedEvent.extracted_tickers &&
                selectedEvent.extracted_tickers.length > 1 && (
                  <div>
                    <p className="data-label mb-2">Related Tickers</p>
                    <div className="flex flex-wrap gap-1">
                      {selectedEvent.extracted_tickers.map((ticker) => (
                        <Link
                          key={ticker}
                          href={`/dashboard/ticker/${ticker}`}
                          className="ticker-chip text-xs hover:bg-accent hover:text-bg-primary transition-colors"
                        >
                          {ticker}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}

              {/* Source Link */}
              {selectedEvent.source_url && (
                <a
                  href={selectedEvent.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-hover transition-colors link-underline"
                >
                  View source
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              )}
            </div>
          ) : (
            <div className="p-12 text-center">
              <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
                <Zap className="h-6 w-6 text-text-quaternary" />
              </div>
              <p className="text-sm font-medium text-text-secondary mb-1">
                Select a signal
              </p>
              <p className="text-xs text-text-tertiary">
                Click on a signal to see details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
