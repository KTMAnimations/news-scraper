'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, Zap, Clock, BarChart3, Activity, ArrowUpRight, ArrowDownRight } from 'lucide-react';
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
          <h1 className="font-serif text-3xl text-ink mb-1">Dashboard</h1>
          <p className="text-ink-muted">
            Real-time sentiment signals for micro-cap securities
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 card rounded-lg">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              wsStatus === 'connected' ? 'bg-bullish live-indicator' : 'bg-bearish'
            )}
          />
          <span className="text-sm text-ink-muted">
            {wsStatus === 'connected' ? 'Live Feed Active' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card rounded-xl p-5 group hover:shadow-card-hover transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-2xs text-ink-faint uppercase tracking-wider mb-1">Total Events</p>
              <p className="font-mono text-3xl font-semibold text-ink">
                {stats.totalEvents}
              </p>
              <p className="text-xs text-ink-muted mt-1 flex items-center gap-1">
                <ArrowUpRight className="h-3 w-3 text-bullish" />
                <span className="text-bullish">+12%</span>
                <span>vs yesterday</span>
              </p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-paper-warm flex items-center justify-center group-hover:bg-ink group-hover:text-paper transition-colors">
              <BarChart3 className="h-6 w-6 text-ink-muted group-hover:text-paper" />
            </div>
          </div>
        </div>

        <div className="card rounded-xl p-5 group hover:shadow-card-hover transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-2xs text-ink-faint uppercase tracking-wider mb-1">Bullish Signals</p>
              <p className="font-mono text-3xl font-semibold text-bullish">
                {stats.bullishEvents}
              </p>
              <p className="text-xs text-ink-muted mt-1 flex items-center gap-1">
                <ArrowUpRight className="h-3 w-3 text-bullish" />
                <span className="text-bullish">+8%</span>
                <span>vs yesterday</span>
              </p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-bullish-bg flex items-center justify-center">
              <TrendingUp className="h-6 w-6 text-bullish" />
            </div>
          </div>
        </div>

        <div className="card rounded-xl p-5 group hover:shadow-card-hover transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-2xs text-ink-faint uppercase tracking-wider mb-1">Bearish Signals</p>
              <p className="font-mono text-3xl font-semibold text-bearish">
                {stats.bearishEvents}
              </p>
              <p className="text-xs text-ink-muted mt-1 flex items-center gap-1">
                <ArrowDownRight className="h-3 w-3 text-bearish" />
                <span className="text-bearish">-5%</span>
                <span>vs yesterday</span>
              </p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-bearish-bg flex items-center justify-center">
              <TrendingDown className="h-6 w-6 text-bearish" />
            </div>
          </div>
        </div>

        <div className="card rounded-xl p-5 group hover:shadow-card-hover transition-shadow">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-2xs text-ink-faint uppercase tracking-wider mb-1">High Alpha</p>
              <p className="font-mono text-3xl font-semibold text-accent">
                {stats.highAlphaCount}
              </p>
              <p className="text-xs text-ink-muted mt-1 flex items-center gap-1">
                <Zap className="h-3 w-3 text-accent" />
                <span className="text-accent">3 new</span>
                <span>this hour</span>
              </p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-accent-light flex items-center justify-center">
              <Zap className="h-6 w-6 text-accent" />
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Event feed */}
        <div className="lg:col-span-2 card rounded-xl overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-ink-muted" />
              <h2 className="font-serif text-lg text-ink">Latest Events</h2>
            </div>
            <span className="text-xs text-ink-faint">
              {events.length} events
            </span>
          </div>
          <div className="max-h-[600px] overflow-y-auto custom-scrollbar">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 rounded-lg bg-ink animate-pulse mx-auto mb-3" />
                <p className="text-sm text-ink-muted">Loading events...</p>
              </div>
            ) : events.length === 0 ? (
              <div className="p-8 text-center">
                <div className="w-12 h-12 rounded-xl bg-paper-warm mx-auto mb-3 flex items-center justify-center">
                  <Activity className="h-6 w-6 text-ink-faint" />
                </div>
                <p className="text-sm text-ink-muted mb-1">No events yet</p>
                <p className="text-xs text-ink-faint">Events will appear here in real-time</p>
              </div>
            ) : (
              events.slice(0, 20).map((event) => (
                <EventCard key={event.id} event={event} />
              ))
            )}
          </div>
        </div>

        {/* High alpha sidebar */}
        <div className="card rounded-xl overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between bg-accent-light">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-accent" />
              <h2 className="font-serif text-lg text-ink">High Alpha Signals</h2>
            </div>
            <span className="px-2 py-0.5 bg-accent text-paper text-xs font-medium rounded-full">
              {highAlphaEvents.length}
            </span>
          </div>
          <div className="max-h-[552px] overflow-y-auto custom-scrollbar">
            {highAlphaEvents.length === 0 ? (
              <div className="p-8 text-center">
                <div className="w-12 h-12 rounded-xl bg-accent-light mx-auto mb-3 flex items-center justify-center">
                  <Zap className="h-6 w-6 text-accent" />
                </div>
                <p className="text-sm text-ink-muted mb-1">No high-alpha signals</p>
                <p className="text-xs text-ink-faint">Signals with alpha &gt;70 appear here</p>
              </div>
            ) : (
              highAlphaEvents.slice(0, 10).map((event) => (
                <div key={event.id} className="p-4 hover:bg-paper-warm transition-colors border-b border-border last:border-0">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-accent font-semibold text-sm px-2 py-0.5 bg-accent-light rounded">
                      {event.ticker}
                    </span>
                    <span className="text-xs text-ink-faint flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatRelativeTime(event.event_time)}
                    </span>
                  </div>
                  <p className="text-sm text-ink font-medium line-clamp-2 leading-snug mb-3">
                    {event.headline}
                  </p>
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        'flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full',
                        event.direction === 'BULLISH'
                          ? 'bg-bullish-bg text-bullish'
                          : event.direction === 'BEARISH'
                          ? 'bg-bearish-bg text-bearish'
                          : 'bg-paper-warm text-ink-muted'
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
                      <span className="font-mono text-lg font-semibold text-accent">
                        {((event.alpha_score || 0) * 100).toFixed(0)}
                      </span>
                      <span className="text-2xs text-ink-faint ml-1">alpha</span>
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
