'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, Minus, Zap, Clock } from 'lucide-react';
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
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400">
            Real-time sentiment signals for micro-cap securities
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              wsStatus === 'connected' ? 'bg-green-500' : 'bg-red-500'
            )}
          />
          <span className="text-sm text-slate-400">
            {wsStatus === 'connected' ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">Total Events</p>
              <p className="text-2xl font-semibold text-white">
                {stats.totalEvents}
              </p>
            </div>
            <div className="p-2 bg-slate-700/50 rounded-lg">
              <Clock className="h-5 w-5 text-slate-400" />
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">Bullish Signals</p>
              <p className="text-2xl font-semibold text-bullish">
                {stats.bullishEvents}
              </p>
            </div>
            <div className="p-2 bg-bullish/10 rounded-lg">
              <TrendingUp className="h-5 w-5 text-bullish" />
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">Bearish Signals</p>
              <p className="text-2xl font-semibold text-bearish">
                {stats.bearishEvents}
              </p>
            </div>
            <div className="p-2 bg-bearish/10 rounded-lg">
              <TrendingDown className="h-5 w-5 text-bearish" />
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">High Alpha</p>
              <p className="text-2xl font-semibold text-brand-400">
                {stats.highAlphaCount}
              </p>
            </div>
            <div className="p-2 bg-brand-500/10 rounded-lg">
              <Zap className="h-5 w-5 text-brand-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Event feed */}
        <div className="lg:col-span-2 bg-slate-800/50 border border-slate-700 rounded-lg">
          <div className="p-4 border-b border-slate-700">
            <h2 className="text-lg font-semibold text-white">Latest Events</h2>
          </div>
          <div className="divide-y divide-slate-700 max-h-[600px] overflow-y-auto custom-scrollbar">
            {isLoading ? (
              <div className="p-8 text-center text-slate-400">
                Loading events...
              </div>
            ) : events.length === 0 ? (
              <div className="p-8 text-center text-slate-400">
                No events yet. Events will appear here in real-time.
              </div>
            ) : (
              events.slice(0, 20).map((event) => (
                <EventCard key={event.id} event={event} />
              ))
            )}
          </div>
        </div>

        {/* High alpha sidebar */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg">
          <div className="p-4 border-b border-slate-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white flex items-center">
              <Zap className="h-5 w-5 text-brand-400 mr-2" />
              High Alpha Signals
            </h2>
          </div>
          <div className="divide-y divide-slate-700 max-h-[600px] overflow-y-auto custom-scrollbar">
            {highAlphaEvents.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-sm">
                High-alpha events will appear here when detected.
              </div>
            ) : (
              highAlphaEvents.slice(0, 10).map((event) => (
                <div key={event.id} className="p-4 hover:bg-slate-700/30">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-brand-400 font-medium">
                      {event.ticker}
                    </span>
                    <span className="text-xs text-slate-500">
                      {formatRelativeTime(event.event_time)}
                    </span>
                  </div>
                  <p className="text-sm text-white line-clamp-2">
                    {event.headline}
                  </p>
                  <div className="mt-2 flex items-center space-x-2">
                    <span
                      className={cn(
                        'text-xs font-medium',
                        event.direction === 'BULLISH'
                          ? 'text-bullish'
                          : event.direction === 'BEARISH'
                          ? 'text-bearish'
                          : 'text-slate-400'
                      )}
                    >
                      {event.direction}
                    </span>
                    <span className="text-xs text-slate-500">
                      Alpha: {((event.alpha_score || 0) * 100).toFixed(0)}
                    </span>
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
