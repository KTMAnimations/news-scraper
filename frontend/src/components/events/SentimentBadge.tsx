'use client';

import { cn } from '@/lib/utils';
import type { SentimentLabel } from '@/types/events';

interface SentimentBadgeProps {
  sentiment: SentimentLabel;
  confidence?: number;
  showConfidence?: boolean;
}

export function SentimentBadge({
  sentiment,
  confidence,
  showConfidence = true,
}: SentimentBadgeProps) {
  const badgeClasses = cn(
    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
    sentiment === 'positive' && 'badge-bullish',
    sentiment === 'negative' && 'badge-bearish',
    sentiment === 'neutral' && 'badge-neutral'
  );

  const label =
    sentiment === 'positive'
      ? 'Positive'
      : sentiment === 'negative'
      ? 'Negative'
      : 'Neutral';

  return (
    <span className={badgeClasses}>
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full',
          sentiment === 'positive' && 'bg-bullish',
          sentiment === 'negative' && 'bg-bearish',
          sentiment === 'neutral' && 'bg-ink-faint'
        )}
      />
      {label}
      {showConfidence && confidence !== undefined && (
        <span className="font-mono opacity-70">({(confidence * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
