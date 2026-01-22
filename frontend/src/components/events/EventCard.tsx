'use client';

import { useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { Event } from '@/types/events';
import {
  cn,
  formatRelativeTime,
  formatDateTime,
  getUrgencyColor,
} from '@/lib/utils';
import { SentimentBadge } from './SentimentBadge';

interface EventCardProps {
  event: Event;
  compact?: boolean;
}

export function EventCard({ event, compact = false }: EventCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const DirectionIcon =
    event.direction === 'BULLISH'
      ? TrendingUp
      : event.direction === 'BEARISH'
      ? TrendingDown
      : Minus;

  const directionColor =
    event.direction === 'BULLISH'
      ? 'text-bullish'
      : event.direction === 'BEARISH'
      ? 'text-bearish'
      : 'text-slate-400';

  return (
    <div
      className={cn(
        'p-4 hover:bg-slate-700/30 transition-colors cursor-pointer',
        isExpanded && 'bg-slate-700/20'
      )}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {/* Ticker */}
            <span className="font-mono text-brand-400 font-semibold text-sm">
              {event.ticker}
            </span>

            {/* Event type badge */}
            <span className="px-2 py-0.5 bg-slate-700 text-slate-300 text-xs rounded">
              {event.event_type.replace(/_/g, ' ')}
            </span>

            {/* Urgency indicator */}
            {event.urgency && (
              <span
                className={cn(
                  'w-2 h-2 rounded-full',
                  getUrgencyColor(event.urgency)
                )}
                title={`${event.urgency} urgency`}
              />
            )}
          </div>

          {/* Headline */}
          <h3 className={cn('text-white', compact ? 'text-sm' : 'text-base')}>
            {event.headline}
          </h3>

          {/* Meta info */}
          <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
            <span>{formatRelativeTime(event.event_time)}</span>
            {event.source_name && (
              <>
                <span>•</span>
                <span>{event.source_name}</span>
              </>
            )}
          </div>
        </div>

        {/* Right side - scores */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          {/* Direction */}
          <div className={cn('flex items-center gap-1', directionColor)}>
            <DirectionIcon className="h-4 w-4" />
            <span className="text-sm font-medium">{event.direction}</span>
          </div>

          {/* Alpha score */}
          {event.alpha_score !== undefined && (
            <div className="text-right">
              <div
                className={cn(
                  'text-lg font-semibold',
                  Math.abs(event.alpha_score) >= 0.7
                    ? 'text-brand-400'
                    : Math.abs(event.alpha_score) >= 0.4
                    ? 'text-amber-400'
                    : 'text-slate-400'
                )}
              >
                {(event.alpha_score * 100).toFixed(0)}
              </div>
              <div className="text-xs text-slate-500">Alpha</div>
            </div>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-slate-700 animate-fade-in">
          {/* Summary */}
          {event.summary && (
            <p className="text-sm text-slate-300 mb-4">{event.summary}</p>
          )}

          {/* Details grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {/* Sentiment */}
            {event.sentiment_label && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Sentiment</div>
                <SentimentBadge
                  sentiment={event.sentiment_label}
                  confidence={event.sentiment_confidence}
                />
              </div>
            )}

            {/* Event time */}
            <div>
              <div className="text-xs text-slate-500 mb-1">Event Time</div>
              <div className="text-sm text-white">
                {formatDateTime(event.event_time)}
              </div>
            </div>

            {/* Extracted tickers */}
            {event.extracted_tickers && event.extracted_tickers.length > 0 && (
              <div>
                <div className="text-xs text-slate-500 mb-1">
                  Related Tickers
                </div>
                <div className="flex flex-wrap gap-1">
                  {event.extracted_tickers.map((ticker) => (
                    <span
                      key={ticker}
                      className="px-1.5 py-0.5 bg-slate-700 text-brand-400 text-xs rounded font-mono"
                    >
                      {ticker}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted people */}
            {event.extracted_people && event.extracted_people.length > 0 && (
              <div>
                <div className="text-xs text-slate-500 mb-1">People</div>
                <div className="text-sm text-white">
                  {event.extracted_people.join(', ')}
                </div>
              </div>
            )}
          </div>

          {/* Source link */}
          {event.source_url && (
            <a
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-brand-400 hover:text-brand-300"
              onClick={(e) => e.stopPropagation()}
            >
              View source
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      )}

      {/* Expand indicator */}
      <div className="flex justify-center mt-2">
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-slate-500" />
        ) : (
          <ChevronDown className="h-4 w-4 text-slate-500" />
        )}
      </div>
    </div>
  );
}
