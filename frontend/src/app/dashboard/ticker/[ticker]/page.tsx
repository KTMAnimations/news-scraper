'use client';

import { useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Clock,
  Star,
  StarOff,
  ExternalLink,
  Bell,
  RefreshCw,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeTime, formatDateTime } from '@/lib/utils';
import { EventCard } from '@/components/events/EventCard';
import { SentimentBadge } from '@/components/events/SentimentBadge';
import { TradingViewChart } from '@/components/charts/TradingViewChart';
import type { Event } from '@/types/events';

// Simple sentiment chart component using div bars
function SentimentChart({ events }: { events: Event[] }) {
  // Group events by hour for the last 24 hours
  const hourlyData = useMemo(() => {
    const now = Date.now();
    const hours: { hour: number; positive: number; negative: number; neutral: number; avgSentiment: number }[] = [];

    for (let i = 23; i >= 0; i--) {
      const hourStart = now - (i + 1) * 60 * 60 * 1000;
      const hourEnd = now - i * 60 * 60 * 1000;

      const hourEvents = events.filter((e) => {
        const eventTime = new Date(e.event_time).getTime();
        return eventTime >= hourStart && eventTime < hourEnd;
      });

      const positive = hourEvents.filter((e) => e.sentiment_label === 'positive').length;
      const negative = hourEvents.filter((e) => e.sentiment_label === 'negative').length;
      const neutral = hourEvents.filter((e) => e.sentiment_label === 'neutral').length;
      const avgSentiment = hourEvents.length > 0
        ? hourEvents.reduce((sum, e) => sum + (e.sentiment_score || 0), 0) / hourEvents.length
        : 0;

      hours.push({ hour: 24 - i, positive, negative, neutral, avgSentiment });
    }

    return hours;
  }, [events]);

  const maxCount = Math.max(...hourlyData.map((h) => h.positive + h.negative + h.neutral), 1);

  return (
    <div className="space-y-3">
      <div className="flex items-end gap-1 h-32">
        {hourlyData.map((data, i) => {
          const total = data.positive + data.negative + data.neutral;
          const height = (total / maxCount) * 100;

          return (
            <div
              key={i}
              className="flex-1 flex flex-col justify-end group relative"
            >
              {total > 0 ? (
                <div
                  className="w-full rounded-t transition-all hover:opacity-80"
                  style={{
                    height: `${height}%`,
                    background: data.avgSentiment > 0
                      ? 'var(--color-positive)'
                      : data.avgSentiment < 0
                      ? 'var(--color-negative)'
                      : 'var(--color-bg-tertiary)',
                  }}
                />
              ) : (
                <div className="w-full h-1 bg-bg-tertiary rounded" />
              )}

              {/* Tooltip */}
              <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 hidden group-hover:block z-10">
                <div className="bg-bg-elevated border border-border rounded-lg p-2 text-xs whitespace-nowrap shadow-lg">
                  <p className="font-medium text-text-primary">{total} events</p>
                  <p className="text-text-tertiary">{data.hour}h ago</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-2xs text-text-quaternary">
        <span>24h ago</span>
        <span>Now</span>
      </div>
    </div>
  );
}

export default function TickerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const ticker = (params.ticker as string).toUpperCase();
  const [timeRange, setTimeRange] = useState(24);

  // Fetch ticker events
  const { data: events = [], isLoading: eventsLoading, refetch } = useQuery({
    queryKey: ['ticker-events', ticker, timeRange],
    queryFn: () => api.getTickerEvents(ticker, 100),
  });

  // Fetch ticker sentiment
  const { data: sentimentData } = useQuery({
    queryKey: ['ticker-sentiment', ticker, timeRange],
    queryFn: () => api.getTickerSentiment(ticker, timeRange),
  });

  // Fetch watchlist to check if ticker is watched
  const { data: watchlist = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => api.getWatchlist(),
  });

  const isWatched = watchlist.some((item) => item.ticker === ticker);

  // Add/remove from watchlist
  const addToWatchlistMutation = useMutation({
    mutationFn: () => api.addToWatchlist(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });

  const removeFromWatchlistMutation = useMutation({
    mutationFn: () => api.removeFromWatchlist(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });

  // Calculate stats from events
  const stats = useMemo(() => {
    const bullish = events.filter((e) => e.direction === 'BULLISH').length;
    const bearish = events.filter((e) => e.direction === 'BEARISH').length;
    const highAlpha = events.filter((e) => Math.abs(e.alpha_score || 0) >= 0.7).length;
    const avgAlpha = events.length > 0
      ? events.reduce((sum, e) => sum + (e.alpha_score || 0), 0) / events.length
      : 0;

    return { bullish, bearish, highAlpha, avgAlpha };
  }, [events]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.back()}
            className="p-2 hover:bg-hover rounded-lg transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-text-secondary" />
          </button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-text-primary tracking-tight">
                {ticker}
              </h1>
              <button
                onClick={() =>
                  isWatched
                    ? removeFromWatchlistMutation.mutate()
                    : addToWatchlistMutation.mutate()
                }
                className={cn(
                  'p-2 rounded-lg transition-colors',
                  isWatched
                    ? 'bg-warning-subtle text-warning'
                    : 'hover:bg-hover text-text-tertiary'
                )}
                title={isWatched ? 'Remove from watchlist' : 'Add to watchlist'}
              >
                {isWatched ? (
                  <Star className="h-5 w-5 fill-current" />
                ) : (
                  <StarOff className="h-5 w-5" />
                )}
              </button>
            </div>
            <p className="text-text-secondary mt-1">
              {events.length} events in the last {timeRange} hours
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="input py-2 text-sm"
          >
            <option value={6}>Last 6 hours</option>
            <option value={24}>Last 24 hours</option>
            <option value={48}>Last 48 hours</option>
            <option value={168}>Last 7 days</option>
          </select>
          <button
            onClick={() => refetch()}
            className="btn btn-secondary flex items-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">Total Events</p>
          <p className="font-mono text-3xl font-bold text-text-primary">
            {events.length}
          </p>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">Bullish</p>
          <p className="font-mono text-3xl font-bold text-positive">
            {stats.bullish}
          </p>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">Bearish</p>
          <p className="font-mono text-3xl font-bold text-negative">
            {stats.bearish}
          </p>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">High Alpha</p>
          <p className="font-mono text-3xl font-bold text-accent">
            {stats.highAlpha}
          </p>
        </div>

        <div className="card-interactive rounded-2xl p-5">
          <p className="data-label mb-2">Avg Sentiment</p>
          <div className="flex items-center gap-2">
            <p
              className={cn(
                'font-mono text-3xl font-bold',
                (sentimentData?.avg_sentiment || 0) > 0
                  ? 'text-positive'
                  : (sentimentData?.avg_sentiment || 0) < 0
                  ? 'text-negative'
                  : 'text-text-tertiary'
              )}
            >
              {((sentimentData?.avg_sentiment || 0) * 100).toFixed(0)}
            </p>
            {(sentimentData?.avg_sentiment || 0) > 0 ? (
              <TrendingUp className="h-5 w-5 text-positive" />
            ) : (sentimentData?.avg_sentiment || 0) < 0 ? (
              <TrendingDown className="h-5 w-5 text-negative" />
            ) : null}
          </div>
        </div>
      </div>

      {/* TradingView Chart */}
      <div className="card rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-text-primary">
            {ticker} Price Chart
          </h2>
          <a
            href={`https://www.tradingview.com/symbols/${ticker}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-accent transition-colors"
          >
            <span>Open in TradingView</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
        <TradingViewChart symbol={ticker} theme="dark" height={500} interval="D" />
      </div>

      {/* Chart & Sentiment Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sentiment Chart */}
        <div className="card rounded-2xl p-5">
          <h2 className="text-lg font-semibold text-text-primary mb-5">
            Event Activity (Last 24h)
          </h2>
          <SentimentChart events={events} />
          <div className="flex items-center justify-center gap-6 mt-5">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-positive" />
              <span className="text-xs text-text-tertiary">Positive</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-negative" />
              <span className="text-xs text-text-tertiary">Negative</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-bg-tertiary" />
              <span className="text-xs text-text-tertiary">Neutral</span>
            </div>
          </div>
        </div>

        {/* Sentiment Breakdown */}
        <div className="card rounded-2xl p-5">
          <h2 className="text-lg font-semibold text-text-primary mb-5">
            Sentiment Analysis
          </h2>

          <div className="space-y-4">
            {/* Sentiment Bar */}
            <div>
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-text-secondary">Overall Sentiment</span>
                <span
                  className={cn(
                    'font-medium',
                    (sentimentData?.avg_sentiment || 0) > 0.2
                      ? 'text-positive'
                      : (sentimentData?.avg_sentiment || 0) < -0.2
                      ? 'text-negative'
                      : 'text-text-tertiary'
                  )}
                >
                  {(sentimentData?.avg_sentiment || 0) > 0.2
                    ? 'Bullish'
                    : (sentimentData?.avg_sentiment || 0) < -0.2
                    ? 'Bearish'
                    : 'Neutral'}
                </span>
              </div>
              <div className="h-3 bg-bg-tertiary rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full transition-all',
                    (sentimentData?.avg_sentiment || 0) > 0
                      ? 'bg-positive'
                      : 'bg-negative'
                  )}
                  style={{
                    width: `${50 + (sentimentData?.avg_sentiment || 0) * 50}%`,
                  }}
                />
              </div>
              <div className="flex justify-between text-2xs text-text-quaternary mt-1">
                <span>Bearish</span>
                <span>Bullish</span>
              </div>
            </div>

            {/* Event Type Distribution */}
            <div className="pt-4 border-t border-border">
              <p className="text-sm text-text-secondary mb-3">Event Types</p>
              <div className="space-y-2">
                {Object.entries(
                  events.reduce(
                    (acc, e) => {
                      acc[e.event_type] = (acc[e.event_type] || 0) + 1;
                      return acc;
                    },
                    {} as Record<string, number>
                  )
                )
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 5)
                  .map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between">
                      <span className="text-sm text-text-tertiary">
                        {type.replace(/_/g, ' ')}
                      </span>
                      <span className="font-mono text-sm text-text-primary">
                        {count}
                      </span>
                    </div>
                  ))}
              </div>
            </div>

            {/* Trend Indicator */}
            <div className="pt-4 border-t border-border">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">Sentiment Trend</span>
                <span
                  className={cn(
                    'flex items-center gap-1.5 text-sm font-medium px-2.5 py-1 rounded-lg',
                    sentimentData?.sentiment_trend === 'improving'
                      ? 'bg-positive-subtle text-positive'
                      : sentimentData?.sentiment_trend === 'declining'
                      ? 'bg-negative-subtle text-negative'
                      : 'bg-bg-tertiary text-text-tertiary'
                  )}
                >
                  {sentimentData?.sentiment_trend === 'improving' ? (
                    <TrendingUp className="h-3.5 w-3.5" />
                  ) : sentimentData?.sentiment_trend === 'declining' ? (
                    <TrendingDown className="h-3.5 w-3.5" />
                  ) : null}
                  {sentimentData?.sentiment_trend || 'Stable'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Events List */}
      <div className="card rounded-2xl overflow-hidden">
        <div className="p-5 border-b border-border">
          <h2 className="text-lg font-semibold text-text-primary">
            Recent Events
          </h2>
        </div>
        <div className="max-h-[600px] overflow-y-auto custom-scrollbar">
          {eventsLoading ? (
            <div className="p-8 text-center">
              <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
              <p className="text-sm text-text-tertiary">Loading events...</p>
            </div>
          ) : events.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
                <span className="text-2xl">📰</span>
              </div>
              <p className="text-sm font-medium text-text-secondary mb-1">
                No events found
              </p>
              <p className="text-xs text-text-tertiary">
                No events found for {ticker} in this time range
              </p>
            </div>
          ) : (
            events.map((event) => <EventCard key={event.id} event={event} />)
          )}
        </div>
      </div>
    </div>
  );
}
