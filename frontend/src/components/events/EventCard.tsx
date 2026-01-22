'use client';

import { useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Clock,
  Zap,
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
      : 'text-ink-muted';

  const directionBg =
    event.direction === 'BULLISH'
      ? 'bg-bullish-bg'
      : event.direction === 'BEARISH'
      ? 'bg-bearish-bg'
      : 'bg-paper-warm';

  const isHighAlpha = event.alpha_score !== undefined && Math.abs(event.alpha_score) >= 0.7;

  return (
    <div
      className={cn(
        'p-4 hover:bg-paper-warm transition-colors cursor-pointer border-b border-border',
        isExpanded && 'bg-paper-warm'
      )}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {/* Ticker */}
            <span className="font-mono text-accent font-semibold text-sm px-2 py-0.5 bg-accent-light rounded">
              {event.ticker}
            </span>

            {/* Event type badge */}
            <span className="px-2 py-0.5 bg-paper-warm border border-border text-ink-muted text-xs rounded">
              {event.event_type.replace(/_/g, ' ')}
            </span>

            {/* High Alpha indicator */}
            {isHighAlpha && (
              <span className="flex items-center gap-1 px-2 py-0.5 bg-accent text-paper text-xs rounded font-medium">
                <Zap className="h-3 w-3" />
                High Alpha
              </span>
            )}

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
          <h3 className={cn('text-ink font-medium leading-snug', compact ? 'text-sm' : 'text-base')}>
            {event.headline}
          </h3>

          {/* Meta info */}
          <div className="flex items-center gap-3 mt-2 text-xs text-ink-faint">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatRelativeTime(event.event_time)}
            </span>
            {event.source_name && (
              <>
                <span className="text-border-strong">•</span>
                <span>{event.source_name}</span>
              </>
            )}
          </div>
        </div>

        {/* Right side - scores */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          {/* Direction */}
          <div className={cn('flex items-center gap-1.5 px-2.5 py-1 rounded-full', directionBg, directionColor)}>
            <DirectionIcon className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">{event.direction}</span>
          </div>

          {/* Alpha score */}
          {event.alpha_score !== undefined && (
            <div className="text-right">
              <div
                className={cn(
                  'font-mono text-xl font-semibold',
                  isHighAlpha
                    ? 'text-accent'
                    : Math.abs(event.alpha_score) >= 0.4
                    ? 'text-ink'
                    : 'text-ink-muted'
                )}
              >
                {(event.alpha_score * 100).toFixed(0)}
              </div>
              <div className="text-2xs text-ink-faint uppercase tracking-wide">Alpha</div>
            </div>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-border">
          {/* Summary */}
          {event.summary && (
            <p className="text-sm text-ink-muted mb-4 leading-relaxed">{event.summary}</p>
          )}

          {/* Details grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {/* Sentiment */}
            {event.sentiment_label && (
              <div>
                <div className="text-2xs text-ink-faint uppercase tracking-wide mb-1.5">Sentiment</div>
                <SentimentBadge
                  sentiment={event.sentiment_label}
                  confidence={event.sentiment_confidence}
                />
              </div>
            )}

            {/* Event time */}
            <div>
              <div className="text-2xs text-ink-faint uppercase tracking-wide mb-1.5">Event Time</div>
              <div className="text-sm text-ink">
                {formatDateTime(event.event_time)}
              </div>
            </div>

            {/* Extracted tickers */}
            {event.extracted_tickers && event.extracted_tickers.length > 0 && (
              <div>
                <div className="text-2xs text-ink-faint uppercase tracking-wide mb-1.5">
                  Related Tickers
                </div>
                <div className="flex flex-wrap gap-1">
                  {event.extracted_tickers.map((ticker) => (
                    <span
                      key={ticker}
                      className="px-1.5 py-0.5 bg-accent-light text-accent text-xs rounded font-mono"
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
                <div className="text-2xs text-ink-faint uppercase tracking-wide mb-1.5">People</div>
                <div className="text-sm text-ink">
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
              className="inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-dark transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              View source
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      )}

      {/* Expand indicator */}
      <div className="flex justify-center mt-2">
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-ink-faint" />
        ) : (
          <ChevronDown className="h-4 w-4 text-ink-faint" />
        )}
      </div>
    </div>
  );
}
