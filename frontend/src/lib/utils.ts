import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { formatDistanceToNow, format } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  return formatDistanceToNow(date, { addSuffix: true });
}

export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return format(date, 'MMM d, yyyy HH:mm:ss');
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return format(date, 'MMM d, yyyy');
}

export function formatAlphaScore(score: number | undefined): string {
  if (score === undefined || score === null) return '-';
  return (score * 100).toFixed(0);
}

export function getAlphaScoreColor(score: number | undefined): string {
  if (score === undefined || score === null) return 'text-muted-foreground';
  if (score >= 0.7) return 'text-bullish';
  if (score >= 0.4) return 'text-amber-500';
  if (score <= -0.4) return 'text-bearish';
  return 'text-muted-foreground';
}

export function getSentimentColor(
  sentiment: 'positive' | 'negative' | 'neutral' | undefined
): string {
  switch (sentiment) {
    case 'positive':
      return 'text-bullish';
    case 'negative':
      return 'text-bearish';
    default:
      return 'text-muted-foreground';
  }
}

export function getDirectionIcon(direction: string | undefined): string {
  switch (direction) {
    case 'BULLISH':
      return '↑';
    case 'BEARISH':
      return '↓';
    default:
      return '→';
  }
}

export function getUrgencyColor(urgency: string | undefined): string {
  switch (urgency) {
    case 'CRITICAL':
      return 'bg-red-500';
    case 'HIGH':
      return 'bg-orange-500';
    case 'MEDIUM':
      return 'bg-yellow-500';
    case 'LOW':
      return 'bg-gray-400';
    default:
      return 'bg-gray-300';
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
}

export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}
