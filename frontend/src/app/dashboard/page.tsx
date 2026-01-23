'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, Clock, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { api } from '@/lib/api';
import { useEventStream } from '@/hooks/useEventStream';
import { useEventStore } from '@/store/eventStore';
import { EventCard } from '@/components/events/EventCard';
import { formatRelativeTime, cn } from '@/lib/utils';

export default function DashboardPage() {
  const { status: wsStatus } = useEventStream({ channel: 'all' });
  const events = useEventStore((state) => state.events);
  const highAlphaEvents = useEventStore((state) => state.highAlphaEvents);
  const setEvents = useEventStore((state) => state.setEvents);

  // Fetch initial events
  const { data: initialEvents, isLoading } = useQuery({
    queryKey: ['events', 'latest'],
    queryFn: () => api.getLatestEvents(50),
  });

  // Set initial events
  useEffect(() => {
    if (initialEvents) {
      setEvents(initialEvents);
    }
  }, [initialEvents, setEvents]);

  // Calculate stats
  const stats = {
    totalEvents: events.length,
    bullishEvents: events.filter((e) => e.direction === 'BULLISH').length,
    bearishEvents: events.filter((e) => e.direction === 'BEARISH').length,
    highAlphaCount: highAlphaEvents.length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-1 tracking-tight">Dashboard</h1>
          <p className="text-text-secondary">
            Real-time sentiment signals for micro-cap securities
          </p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 card rounded-xl">
          <div
            className={cn(
              wsStatus === 'connected' ? 'live-dot' : 'w-2 h-2 rounded-full bg-negative'
            )}
          />
          <span className="text-sm text-text-secondary">
            {wsStatus === 'connected' ? 'Live Feed Active' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-interactive rounded-2xl p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="data-label mb-2">Total Events</p>
              <p className="font-mono text-3xl font-bold text-text-primary">
                {stats.totalEvents}
              </p>
              <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
                <ArrowUpRight className="h-3 w-3 text-positive" />
                <span className="text-positive font-medium">+12%</span>
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
              <p className="font-mono text-3xl font-bold text-positive">
                {stats.bullishEvents}
              </p>
              <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
                <ArrowUpRight className="h-3 w-3 text-positive" />
                <span className="text-positive font-medium">+8%</span>
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
              <p className="font-mono text-3xl font-bold text-negative">
                {stats.bearishEvents}
              </p>
              <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
                <ArrowDownRight className="h-3 w-3 text-negative" />
                <span className="text-negative font-medium">-5%</span>
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
              <p className="font-mono text-3xl font-bold text-accent">
                {stats.highAlphaCount}
              </p>
              <p className="text-xs text-text-tertiary mt-2 flex items-center gap-1">
                <span className="text-accent font-medium">3 new</span>
                <span>this hour</span>
              </p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-accent-subtle flex items-center justify-center">
              <span className="font-mono text-lg font-bold text-accent">α</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Event feed */}
        <div className="lg:col-span-2 card rounded-2xl overflow-hidden">
          <div className="p-5 border-b border-border flex items-center justify-between">
            <h2 className="text-lg font-semibold text-text-primary">Latest Events</h2>
            <span className="text-xs text-text-tertiary bg-bg-tertiary px-2 py-1 rounded-md">
              {events.length} events
            </span>
          </div>
          <div className="max-h-[600px] overflow-y-auto custom-scrollbar">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 skeleton rounded-lg mx-auto mb-3" />
                <p className="text-sm text-text-tertiary">Loading events...</p>
              </div>
            ) : events.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-bg-tertiary mx-auto mb-4 flex items-center justify-center">
                  <span className="text-2xl">📡</span>
                </div>
                <p className="text-sm font-medium text-text-secondary mb-1">No events yet</p>
                <p className="text-xs text-text-tertiary">Events will appear here in real-time</p>
              </div>
            ) : (
              events.slice(0, 20).map((event, i) => (
                <div
                  key={event.id}
                  className={cn(
                    'animate-fade-up opacity-0',
                    i < 5 && `stagger-${i + 1}`
                  )}
                >
                  <EventCard event={event} />
                </div>
              ))
            )}
          </div>
        </div>

        {/* High alpha sidebar */}
        <div className="card rounded-2xl overflow-hidden">
          <div className="p-5 border-b border-border flex items-center justify-between bg-gradient-to-r from-accent/10 to-transparent">
            <h2 className="text-lg font-semibold text-text-primary">High Alpha Signals</h2>
            <span className="px-2.5 py-1 bg-accent text-bg-primary text-xs font-semibold rounded-lg">
              {highAlphaEvents.length}
            </span>
          </div>
          <div className="max-h-[552px] overflow-y-auto custom-scrollbar">
            {highAlphaEvents.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-14 h-14 rounded-2xl bg-accent-subtle mx-auto mb-4 flex items-center justify-center">
                  <span className="font-mono text-2xl font-bold text-accent">α</span>
                </div>
                <p className="text-sm font-medium text-text-secondary mb-1">No high-alpha signals</p>
                <p className="text-xs text-text-tertiary">Signals with alpha &gt;70 appear here</p>
              </div>
            ) : (
              highAlphaEvents.slice(0, 10).map((event, i) => (
                <div
                  key={event.id}
                  className={cn(
                    'p-5 hover:bg-hover transition-colors border-b border-border last:border-0 cursor-pointer group animate-fade-up opacity-0',
                    i < 5 && `stagger-${i + 1}`
                  )}
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <span className="ticker-chip">
                      {event.ticker}
                    </span>
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
      </div>
    </div>
  );
}
