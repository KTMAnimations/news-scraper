'use client';

import { useQuery } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  BarChart3,
  Clock,
  Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

interface TickerStatsPanelProps {
  ticker: string;
  timeRange?: number;
}

export function TickerStatsPanel({ ticker, timeRange = 24 }: TickerStatsPanelProps) {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['ticker-stats', ticker, timeRange],
    queryFn: () => api.getTickerStats(ticker, timeRange),
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Statistics</h3>
        <div className="grid grid-cols-2 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="skeleton h-4 w-20 rounded" />
              <div className="skeleton h-8 w-16 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Statistics</h3>
        <p className="text-sm text-text-tertiary">Unable to load statistics</p>
      </div>
    );
  }

  const TrendIcon = stats.sentiment_trend === 'improving'
    ? TrendingUp
    : stats.sentiment_trend === 'declining'
    ? TrendingDown
    : Minus;

  const trendColor = stats.sentiment_trend === 'improving'
    ? 'text-positive'
    : stats.sentiment_trend === 'declining'
    ? 'text-negative'
    : 'text-text-tertiary';

  const trendBg = stats.sentiment_trend === 'improving'
    ? 'bg-positive-subtle'
    : stats.sentiment_trend === 'declining'
    ? 'bg-negative-subtle'
    : 'bg-bg-tertiary';

  return (
    <div className="card rounded-2xl p-5">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-lg font-semibold text-text-primary">Statistics</h3>
        <span className="text-xs text-text-tertiary">
          Last {stats.time_window_hours}h
        </span>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Event Count */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-text-tertiary">
            <Activity className="h-3.5 w-3.5" />
            <span className="text-xs">Total Events</span>
          </div>
          <p className="font-mono text-2xl font-bold text-text-primary">
            {stats.event_count}
          </p>
        </div>

        {/* Avg Sentiment */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-text-tertiary">
            <BarChart3 className="h-3.5 w-3.5" />
            <span className="text-xs">Avg Sentiment</span>
          </div>
          <p className={cn(
            'font-mono text-2xl font-bold',
            stats.avg_sentiment > 0 ? 'text-positive' :
            stats.avg_sentiment < 0 ? 'text-negative' : 'text-text-tertiary'
          )}>
            {stats.avg_sentiment > 0 ? '+' : ''}{(stats.avg_sentiment * 100).toFixed(0)}
          </p>
        </div>

        {/* Avg Alpha */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-text-tertiary">
            <Zap className="h-3.5 w-3.5" />
            <span className="text-xs">Avg Alpha</span>
          </div>
          <p className={cn(
            'font-mono text-2xl font-bold',
            Math.abs(stats.avg_alpha) >= 0.7 ? 'text-accent' :
            Math.abs(stats.avg_alpha) >= 0.4 ? 'text-text-primary' : 'text-text-tertiary'
          )}>
            {(stats.avg_alpha * 100).toFixed(0)}
          </p>
        </div>

        {/* Sentiment Trend */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-text-tertiary">
            <TrendingUp className="h-3.5 w-3.5" />
            <span className="text-xs">Trend</span>
          </div>
          <div className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-sm font-medium',
            trendBg,
            trendColor
          )}>
            <TrendIcon className="h-4 w-4" />
            <span className="capitalize">{stats.sentiment_trend}</span>
          </div>
        </div>
      </div>

      {/* Direction Breakdown */}
      <div className="mt-5 pt-5 border-t border-border">
        <p className="text-xs text-text-tertiary mb-3">Direction Breakdown</p>
        <div className="flex gap-4">
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-positive">Bullish</span>
              <span className="font-mono text-sm text-positive">{stats.bullish_count}</span>
            </div>
            <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full bg-positive rounded-full transition-all"
                style={{
                  width: stats.event_count > 0
                    ? `${(stats.bullish_count / stats.event_count) * 100}%`
                    : '0%'
                }}
              />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-negative">Bearish</span>
              <span className="font-mono text-sm text-negative">{stats.bearish_count}</span>
            </div>
            <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full bg-negative rounded-full transition-all"
                style={{
                  width: stats.event_count > 0
                    ? `${(stats.bearish_count / stats.event_count) * 100}%`
                    : '0%'
                }}
              />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-text-tertiary">Neutral</span>
              <span className="font-mono text-sm text-text-tertiary">{stats.neutral_count}</span>
            </div>
            <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full bg-text-quaternary rounded-full transition-all"
                style={{
                  width: stats.event_count > 0
                    ? `${(stats.neutral_count / stats.event_count) * 100}%`
                    : '0%'
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* High Alpha Events */}
      {stats.high_alpha_count > 0 && (
        <div className="mt-4 p-3 bg-accent-subtle rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm text-accent font-medium">High Alpha Events</span>
            <span className="font-mono text-lg font-bold text-accent">{stats.high_alpha_count}</span>
          </div>
        </div>
      )}

      {/* Last Event Time */}
      {stats.last_event_time && (
        <div className="mt-4 flex items-center gap-1.5 text-xs text-text-tertiary">
          <Clock className="h-3 w-3" />
          <span>Last event: {formatRelativeTime(stats.last_event_time)}</span>
        </div>
      )}
    </div>
  );
}
