'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Link as LinkIcon,
  Activity,
  ChevronRight,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface RelatedTickersProps {
  ticker: string;
  limit?: number;
}

export function RelatedTickers({ ticker, limit = 8 }: RelatedTickersProps) {
  const { data: relatedData, isLoading, error } = useQuery({
    queryKey: ['related-tickers', ticker, limit],
    queryFn: () => api.getRelatedTickers(ticker, limit),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  if (isLoading) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Related Tickers</h3>
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-bg-secondary">
              <div className="flex items-center gap-3">
                <div className="skeleton h-8 w-16 rounded" />
                <div className="skeleton h-4 w-24 rounded" />
              </div>
              <div className="skeleton h-6 w-12 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !relatedData) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Related Tickers</h3>
        <p className="text-sm text-text-tertiary">Unable to load related tickers</p>
      </div>
    );
  }

  if (relatedData.related.length === 0) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Related Tickers</h3>
        <div className="text-center py-6">
          <LinkIcon className="h-8 w-8 text-text-quaternary mx-auto mb-2" />
          <p className="text-sm text-text-tertiary">No related tickers found</p>
          <p className="text-xs text-text-quaternary mt-1">
            Check back when more events are processed
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="card rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text-primary">Related Tickers</h3>
        <span className="text-xs text-text-tertiary">
          {relatedData.related.length} found
        </span>
      </div>

      <div className="space-y-2">
        {relatedData.related.map((related) => {
          const sentimentColor = related.avg_sentiment > 0.1
            ? 'text-positive'
            : related.avg_sentiment < -0.1
            ? 'text-negative'
            : 'text-text-tertiary';

          const SentimentIcon = related.avg_sentiment > 0.1
            ? TrendingUp
            : related.avg_sentiment < -0.1
            ? TrendingDown
            : Minus;

          return (
            <Link
              key={related.ticker}
              href={`/dashboard/ticker/${related.ticker}`}
              className="flex items-center justify-between p-3 rounded-lg bg-bg-secondary hover:bg-hover transition-colors group"
            >
              <div className="flex items-center gap-3">
                {/* Ticker Symbol */}
                <span className="ticker-chip text-sm font-medium">
                  {related.ticker}
                </span>

                {/* Company Name */}
                {related.company_name && (
                  <span className="text-sm text-text-secondary truncate max-w-[150px]">
                    {related.company_name}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-4">
                {/* Event Count */}
                <div className="flex items-center gap-1.5 text-text-tertiary">
                  <Activity className="h-3.5 w-3.5" />
                  <span className="text-xs font-mono">{related.event_count}</span>
                </div>

                {/* Sentiment */}
                <div className={cn('flex items-center gap-1', sentimentColor)}>
                  <SentimentIcon className="h-3.5 w-3.5" />
                  <span className="text-xs font-mono">
                    {related.avg_sentiment > 0 ? '+' : ''}
                    {(related.avg_sentiment * 100).toFixed(0)}
                  </span>
                </div>

                {/* Arrow */}
                <ChevronRight className="h-4 w-4 text-text-quaternary group-hover:text-accent transition-colors" />
              </div>
            </Link>
          );
        })}
      </div>

      {/* Reason Note */}
      <p className="text-xs text-text-quaternary mt-4 text-center">
        Based on co-mentions and event timing
      </p>
    </div>
  );
}
