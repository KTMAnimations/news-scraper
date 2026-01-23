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
    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium',
    sentiment === 'positive' && 'badge-positive',
    sentiment === 'negative' && 'badge-negative',
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
          sentiment === 'positive' && 'bg-positive',
          sentiment === 'negative' && 'bg-negative',
          sentiment === 'neutral' && 'bg-text-tertiary'
        )}
      />
      {label}
      {showConfidence && confidence !== undefined && (
        <span className="font-mono opacity-70">({(confidence * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
