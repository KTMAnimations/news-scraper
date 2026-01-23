'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import {
  TrendingUp,
  TrendingDown,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Star,
  ChevronRight,
} from 'lucide-react';
import { useLatestEvents, useHighAlphaEvents, useStats } from '@/hooks/useApi';
import { useEventStore } from '@/store/eventStore';
import { EventCard } from '@/components/events/EventCard';
import { WatchlistButton } from '@/components/watchlist/WatchlistButton';
import { useWatchlist } from '@/hooks/useWatchlist';
import { formatRelativeTime, cn } from '@/lib/utils';
import type { Event } from '@/types/events';

function calculateChange(
  current: number,
  previous: number
): { value: number; direction: 'up' | 'down' | 'neutral' } {
  if (previous === 0) return { value: 0, direction: 'neutral' };
  const change = ((current - previous) / previous) * 100;
  return {
    value: Math.abs(Math.round(change)),
    direction: change > 0 ? 'up' : change < 0 ? 'down' : 'neutral',
  };
}

// Stats Widget
export function StatsWidget() {
  const events = useEventStore((state) => state.events);
  const highAlphaEvents = useEventStore((state) => state.highAlphaEvents);

  const { data: statsData } = useStats({
    refetchInterval: 60000,
  });

  const stats = useMemo(() => {
    if (statsData) {
      return {
        totalEvents: statsData.total_events,
        totalChange: calculateChange(statsData.total_events, statsData.total_events_yesterday),
        bullishEvents: statsData.bullish_events,
        bullishChange: calculateChange(statsData.bullish_events, statsData.bullish_events_yesterday),
        bearishEvents: statsData.bearish_events,
        bearishChange: calculateChange(statsData.bearish_events, statsData.bearish_events_yesterday),
        highAlphaCount: statsData.high_alpha_events,
        highAlphaLastHour: statsData.high_alpha_events_last_hour,
      };
    }
    return {
      totalEvents: events.length,
      totalChange: { value: 0, direction: 'neutral' as const },
      bullishEvents: events.filter((e) => e.direction === 'BULLISH').length,
      bullishChange: { value: 0, direction: 'neutral' as const },
      bearishEvents: events.filter((e) => e.direction === 'BEARISH').length,
      bearishChange: { value: 0, direction: 'neutral' as const },
      highAlphaCount: highAlphaEvents.length,
      highAlphaLastHour: 0,
    };
  }, [statsData, events, highAlphaEvents]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 h-full">
      <div className="card-interactive rounded-2xl p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="data-label mb-2">Total Events</p>
            <p className="font-mono text-3xl font-bold text-text-primary">
              {stats.totalEvents}
            </p>
            <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
              {stats.totalChange.direction === 'up' ? (
                <>
                  <ArrowUpRight className="h-3 w-3 text-positive" />
                  <span className="text-positive font-medium">+{stats.totalChange.value}%</span>
                </>
              ) : stats.totalChange.direction === 'down' ? (
                <>
                  <ArrowDownRight className="h-3 w-3 text-negative" />
                  <span className="text-negative font-medium">-{stats.totalChange.value}%</span>
                </>
              ) : (
                <span className="text-text-tertiary font-medium">--</span>
              )}
              <span>vs yesterday</span>
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-bg-tertiary flex items-center justify-center">
            <span className="font-mono text-lg font-bold text-text-secondary">#</span>
          </div>
        </div>
      </div>

      <div className="card-interactive rounded-2xl p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="data-label mb-2">Bullish Signals</p>
            <p className="font-mono text-3xl font-bold text-positive">{stats.bullishEvents}</p>
            <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
              {stats.bullishChange.direction === 'up' ? (
                <>
                  <ArrowUpRight className="h-3 w-3 text-positive" />
                  <span className="text-positive font-medium">+{stats.bullishChange.value}%</span>
                </>
              ) : stats.bullishChange.direction === 'down' ? (
                <>
                  <ArrowDownRight className="h-3 w-3 text-negative" />
                  <span className="text-negative font-medium">-{stats.bullishChange.value}%</span>
                </>
              ) : (
                <span className="text-text-tertiary font-medium">--</span>
              )}
              <span>vs yesterday</span>
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-positive-subtle flex items-center justify-center">
            <TrendingUp className="h-6 w-6 text-positive" />
          </div>
        </div>
      </div>

      <div className="card-interactive rounded-2xl p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="data-label mb-2">Bearish Signals</p>
            <p className="font-mono text-3xl font-bold text-negative">{stats.bearishEvents}</p>
            <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
              {stats.bearishChange.direction === 'up' ? (
                <>
                  <ArrowUpRight className="h-3 w-3 text-negative" />
                  <span className="text-negative font-medium">+{stats.bearishChange.value}%</span>
                </>
              ) : stats.bearishChange.direction === 'down' ? (
                <>
                  <ArrowDownRight className="h-3 w-3 text-positive" />
                  <span className="text-positive font-medium">-{stats.bearishChange.value}%</span>
                </>
              ) : (
                <span className="text-text-tertiary font-medium">--</span>
              )}
              <span>vs yesterday</span>
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-negative-subtle flex items-center justify-center">
            <TrendingDown className="h-6 w-6 text-negative" />
          </div>
        </div>
      </div>

      <div className="card-interactive rounded-2xl p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="data-label mb-2">High Alpha</p>
            <p className="font-mono text-3xl font-bold text-accent">{stats.highAlphaCount}</p>
            <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
              <span className="text-accent font-medium">{stats.highAlphaLastHour} new</span>
              <span>this hour</span>
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-accent-subtle flex items-center justify-center">
            <span className="font-mono text-lg font-bold text-accent">a</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Event Feed Widget
export function EventFeedWidget() {
  const events = useEventStore((state) => state.events);
  const { data: latestEvents, isLoading } = useLatestEvents(20);

  const displayEvents = latestEvents || events.slice(0, 20);

  return (
    <div className="card rounded-2xl overflow-hidden h-full flex flex-col">
      <div className="p-4 border-b border-border flex items-center justify-between shrink-0">
        <h2 className="text-lg font-semibold text-text-primary">Latest Events</h2>
        <Link
          href="/dashboard/feed"
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
        >
          View All
          <ChevronRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
            <p className="text-sm text-text-tertiary">Loading events...</p>
          </div>
        ) : displayEvents.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
              <span className="text-2xl">📡</span>
            </div>
            <p className="text-sm font-medium text-text-secondary mb-1">No events yet</p>
            <p className="text-xs text-text-tertiary">Events will appear here in real-time</p>
          </div>
        ) : (
          displayEvents.map((event: Event) => <EventCard key={event.id} event={event} />)
        )}
      </div>
    </div>
  );
}

// High Alpha Widget
export function HighAlphaWidget() {
  const highAlphaEventsStore = useEventStore((state) => state.highAlphaEvents);
  const { data: highAlphaData } = useHighAlphaEvents(0.5, 10);

  const displayEvents = highAlphaData || highAlphaEventsStore.slice(0, 10);

  return (
    <div className="card rounded-2xl overflow-hidden h-full flex flex-col">
      <div className="p-4 border-b border-border flex items-center justify-between bg-gradient-to-r from-accent/10 to-transparent shrink-0">
        <h2 className="text-lg font-semibold text-text-primary">High Alpha Signals</h2>
        <span className="px-2.5 py-1 bg-accent text-bg-primary text-xs font-semibold rounded-lg">
          {displayEvents.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {displayEvents.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-accent-subtle mx-auto mb-4 flex items-center justify-center">
              <span className="font-mono text-2xl font-bold text-accent">a</span>
            </div>
            <p className="text-sm font-medium text-text-secondary mb-1">No high-alpha signals</p>
            <p className="text-xs text-text-tertiary">Signals with alpha &gt;70 appear here</p>
          </div>
        ) : (
          displayEvents.map((event: Event) => (
            <div
              key={event.id}
              className="p-4 hover:bg-hover transition-colors border-b border-border last:border-0 cursor-pointer group"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Link
                    href={`/dashboard/ticker/${event.ticker}`}
                    onClick={(e) => e.stopPropagation()}
                    className="ticker-chip hover:bg-accent hover:text-bg-primary transition-colors"
                  >
                    {event.ticker}
                  </Link>
                  <WatchlistButton ticker={event.ticker} variant="compact" />
                </div>
                <span className="text-xs text-text-tertiary flex items-center gap-1.5">
                  <Clock className="h-3 w-3" />
                  {formatRelativeTime(event.event_time)}
                </span>
              </div>
              <p className="text-sm text-text-primary font-medium line-clamp-2 leading-snug mb-3 group-hover:text-accent transition-colors">
                {event.headline}
              </p>
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    'flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg',
                    event.direction === 'BULLISH'
                      ? 'bg-positive-subtle text-positive'
                      : event.direction === 'BEARISH'
                      ? 'bg-negative-subtle text-negative'
                      : 'bg-bg-tertiary text-text-tertiary'
                  )}
                >
                  {event.direction === 'BULLISH' ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : event.direction === 'BEARISH' ? (
                    <TrendingDown className="h-3 w-3" />
                  ) : null}
                  {event.direction}
                </span>
                <div className="text-right">
                  <span className="font-mono text-xl font-bold text-accent">
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
  );
}

// Watchlist Widget
export function WatchlistWidget() {
  const { items, isLoading } = useWatchlist();

  return (
    <div className="card rounded-2xl overflow-hidden h-full flex flex-col">
      <div className="p-4 border-b border-border flex items-center justify-between shrink-0">
        <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
          <Star className="h-5 w-5 text-warning" />
          Watchlist
        </h2>
        <Link
          href="/dashboard/watchlist"
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
        >
          Manage
          <ChevronRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
            <p className="text-sm text-text-tertiary">Loading watchlist...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-warning-subtle mx-auto mb-4 flex items-center justify-center">
              <Star className="h-6 w-6 text-warning" />
            </div>
            <p className="text-sm font-medium text-text-secondary mb-1">No tickers watched</p>
            <p className="text-xs text-text-tertiary mb-4">
              Add tickers to track your favorites
            </p>
            <Link href="/dashboard/watchlist" className="btn btn-primary text-sm">
              Add Tickers
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {items.slice(0, 10).map((item) => (
              <Link
                key={item.ticker}
                href={`/dashboard/ticker/${item.ticker}`}
                className="flex items-center justify-between p-4 hover:bg-hover transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <Star className="h-4 w-4 text-warning fill-current" />
                  <div>
                    <span className="ticker-chip group-hover:bg-accent group-hover:text-bg-primary transition-colors">
                      {item.ticker}
                    </span>
                    {item.notes && (
                      <p className="text-xs text-text-tertiary mt-1 line-clamp-1">
                        {item.notes}
                      </p>
                    )}
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-text-quaternary group-hover:text-text-secondary transition-colors" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Sentiment Chart Widget (placeholder)
export function SentimentChartWidget() {
  const events = useEventStore((state) => state.events);

  const sentimentData = useMemo(() => {
    const positive = events.filter((e) => e.sentiment_label === 'positive').length;
    const negative = events.filter((e) => e.sentiment_label === 'negative').length;
    const neutral = events.filter((e) => e.sentiment_label === 'neutral').length;
    const total = positive + negative + neutral || 1;

    return {
      positive: Math.round((positive / total) * 100),
      negative: Math.round((negative / total) * 100),
      neutral: Math.round((neutral / total) * 100),
      positiveCount: positive,
      negativeCount: negative,
      neutralCount: neutral,
    };
  }, [events]);

  return (
    <div className="card rounded-2xl p-5 h-full flex flex-col">
      <h2 className="text-lg font-semibold text-text-primary mb-4">Sentiment Overview</h2>

      <div className="flex-1 flex flex-col justify-center">
        {/* Sentiment Bar */}
        <div className="h-6 rounded-full overflow-hidden flex bg-bg-tertiary mb-6">
          {sentimentData.positive > 0 && (
            <div
              className="bg-positive transition-all"
              style={{ width: `${sentimentData.positive}%` }}
            />
          )}
          {sentimentData.neutral > 0 && (
            <div
              className="bg-bg-secondary transition-all"
              style={{ width: `${sentimentData.neutral}%` }}
            />
          )}
          {sentimentData.negative > 0 && (
            <div
              className="bg-negative transition-all"
              style={{ width: `${sentimentData.negative}%` }}
            />
          )}
        </div>

        {/* Legend */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-sm bg-positive" />
              <span className="text-xs text-text-tertiary">Positive</span>
            </div>
            <p className="font-mono text-2xl font-bold text-positive">
              {sentimentData.positive}%
            </p>
            <p className="text-xs text-text-quaternary">{sentimentData.positiveCount} events</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-sm bg-bg-secondary" />
              <span className="text-xs text-text-tertiary">Neutral</span>
            </div>
            <p className="font-mono text-2xl font-bold text-text-secondary">
              {sentimentData.neutral}%
            </p>
            <p className="text-xs text-text-quaternary">{sentimentData.neutralCount} events</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-sm bg-negative" />
              <span className="text-xs text-text-tertiary">Negative</span>
            </div>
            <p className="font-mono text-2xl font-bold text-negative">
              {sentimentData.negative}%
            </p>
            <p className="text-xs text-text-quaternary">{sentimentData.negativeCount} events</p>
          </div>
        </div>
      </div>
    </div>
  );
}
