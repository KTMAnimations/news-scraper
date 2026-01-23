'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Clock,
} from 'lucide-react';
import type { Event } from '@/types/events';
import {
  cn,
  formatRelativeTime,
  formatDateTime,
} from '@/lib/utils';
import { SentimentBadge } from './SentimentBadge';
import { WatchlistButton } from '@/components/watchlist/WatchlistButton';

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
      ? 'text-positive'
      : event.direction === 'BEARISH'
      ? 'text-negative'
      : 'text-text-tertiary';

  const directionBg =
    event.direction === 'BULLISH'
      ? 'bg-positive-subtle'
      : event.direction === 'BEARISH'
      ? 'bg-negative-subtle'
      : 'bg-bg-tertiary';

  const isHighAlpha = event.alpha_score !== undefined && Math.abs(event.alpha_score) >= 0.7;

  return (
    <div
      className={cn(
        'p-5 hover:bg-hover transition-colors cursor-pointer border-b border-border group',
        isExpanded && 'bg-bg-secondary'
      )}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2.5 flex-wrap">
            {/* Ticker */}
            <Link
              href={`/dashboard/ticker/${event.ticker}`}
              onClick={(e) => e.stopPropagation()}
              className="ticker-chip hover:bg-accent hover:text-bg-primary transition-colors"
            >
              {event.ticker}
            </Link>

            {/* Watchlist button */}
            <WatchlistButton ticker={event.ticker} variant="compact" showLabel />

            {/* Event type badge */}
            <span className="badge badge-neutral">
              {event.event_type.replace(/_/g, ' ')}
            </span>

            {/* High Alpha indicator */}
            {isHighAlpha && (
              <span className="badge badge-accent font-medium">
                High Alpha
              </span>
            )}
          </div>

          {/* Headline */}
          <h3 className={cn(
            'text-text-primary font-medium leading-snug group-hover:text-accent transition-colors',
            compact ? 'text-sm' : 'text-base'
          )}>
            {event.headline}
          </h3>

          {/* Meta info */}
          <div className="flex items-center gap-3 mt-2.5 text-xs text-text-tertiary">
            <span className="flex items-center gap-1.5">
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
        <div className="flex flex-col items-end gap-2.5 shrink-0">
          {/* Direction */}
          <div className={cn('flex items-center gap-1.5 px-2.5 py-1 rounded-lg', directionBg, directionColor)}>
            <DirectionIcon className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">{event.direction}</span>
          </div>

          {/* Alpha score */}
          {event.alpha_score !== undefined && (
            <div className="text-right">
              <div
                className={cn(
                  'font-mono text-2xl font-bold',
                  isHighAlpha
                    ? 'text-accent'
                    : Math.abs(event.alpha_score) >= 0.4
                    ? 'text-text-primary'
                    : 'text-text-tertiary'
                )}
              >
                {(event.alpha_score * 100).toFixed(0)}
              </div>
              <div className="data-label">Alpha</div>
            </div>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="mt-5 pt-5 border-t border-border animate-fade-in">
          {/* Summary */}
          {event.summary && (
            <p className="text-sm text-text-secondary mb-5 leading-relaxed">{event.summary}</p>
          )}

          {/* Details grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-5">
            {/* Sentiment */}
            {event.sentiment_label && (
              <div>
                <div className="data-label mb-2">Sentiment</div>
                <SentimentBadge
                  sentiment={event.sentiment_label}
                  confidence={event.sentiment_confidence}
                />
              </div>
            )}

            {/* Event time */}
            <div>
              <div className="data-label mb-2">Event Time</div>
              <div className="text-sm text-text-primary">
                {formatDateTime(event.event_time)}
              </div>
            </div>

            {/* Extracted tickers */}
            {event.extracted_tickers && event.extracted_tickers.length > 0 && (
              <div>
                <div className="data-label mb-2">Related Tickers</div>
                <div className="flex flex-wrap gap-1">
                  {event.extracted_tickers.map((ticker) => (
                    <Link
                      key={ticker}
                      href={`/dashboard/ticker/${ticker}`}
                      onClick={(e) => e.stopPropagation()}
                      className="ticker-chip text-xs hover:bg-accent hover:text-bg-primary transition-colors"
                    >
                      {ticker}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted people */}
            {event.extracted_people && event.extracted_people.length > 0 && (
              <div>
                <div className="data-label mb-2">People</div>
                <div className="text-sm text-text-primary">
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
              className="inline-flex items-center gap-1.5 text-sm text-accent hover:text-accent-hover transition-colors link-underline"
              onClick={(e) => e.stopPropagation()}
            >
              View source
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      )}

      {/* Expand indicator */}
      <div className="flex justify-center mt-3">
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-text-quaternary" />
        ) : (
          <ChevronDown className="h-4 w-4 text-text-quaternary" />
        )}
      </div>
    </div>
  );
}
