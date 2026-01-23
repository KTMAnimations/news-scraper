import {
  cn,
  formatRelativeTime,
  formatDateTime,
  formatDate,
  formatAlphaScore,
  getAlphaScoreColor,
  getSentimentColor,
  getDirectionIcon,
  getUrgencyColor,
  truncate,
  formatCurrency,
  formatNumber,
  debounce,
} from '@/lib/utils';

describe('cn (class name utility)', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles conditional classes', () => {
    expect(cn('foo', false && 'bar', 'baz')).toBe('foo baz');
    expect(cn('foo', true && 'bar', 'baz')).toBe('foo bar baz');
  });

  it('handles arrays', () => {
    expect(cn(['foo', 'bar'])).toBe('foo bar');
  });

  it('deduplicates tailwind classes', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });

  it('handles undefined and null', () => {
    expect(cn('foo', undefined, null, 'bar')).toBe('foo bar');
  });
});

describe('formatRelativeTime', () => {
  it('formats recent times', () => {
    const now = new Date();
    const result = formatRelativeTime(now.toISOString());
    expect(result).toContain('ago');
  });

  it('handles past dates', () => {
    const pastDate = new Date('2025-01-01T00:00:00Z');
    const result = formatRelativeTime(pastDate.toISOString());
    expect(result).toContain('ago');
  });
});

describe('formatDateTime', () => {
  it('formats date with time', () => {
    const result = formatDateTime('2026-01-23T15:30:45Z');
    expect(result).toMatch(/Jan 23, 2026/);
    expect(result).toMatch(/\d{2}:\d{2}:\d{2}/);
  });
});

describe('formatDate', () => {
  it('formats date without time', () => {
    const result = formatDate('2026-01-23T15:30:45Z');
    expect(result).toBe('Jan 23, 2026');
  });
});

describe('formatAlphaScore', () => {
  it('formats score as percentage', () => {
    expect(formatAlphaScore(0.75)).toBe('75');
    expect(formatAlphaScore(0.5)).toBe('50');
    expect(formatAlphaScore(1)).toBe('100');
    expect(formatAlphaScore(0)).toBe('0');
  });

  it('handles undefined', () => {
    expect(formatAlphaScore(undefined)).toBe('-');
  });

  it('handles null', () => {
    expect(formatAlphaScore(null as any)).toBe('-');
  });
});

describe('getAlphaScoreColor', () => {
  it('returns bullish color for high positive scores', () => {
    expect(getAlphaScoreColor(0.75)).toBe('text-bullish');
    expect(getAlphaScoreColor(0.9)).toBe('text-bullish');
  });

  it('returns amber for medium scores', () => {
    expect(getAlphaScoreColor(0.5)).toBe('text-amber-500');
    expect(getAlphaScoreColor(0.6)).toBe('text-amber-500');
  });

  it('returns bearish color for low scores', () => {
    expect(getAlphaScoreColor(-0.5)).toBe('text-bearish');
    expect(getAlphaScoreColor(-0.8)).toBe('text-bearish');
  });

  it('returns muted color for neutral scores', () => {
    expect(getAlphaScoreColor(0.2)).toBe('text-muted-foreground');
    expect(getAlphaScoreColor(-0.2)).toBe('text-muted-foreground');
  });

  it('handles undefined', () => {
    expect(getAlphaScoreColor(undefined)).toBe('text-muted-foreground');
  });
});

describe('getSentimentColor', () => {
  it('returns bullish color for positive sentiment', () => {
    expect(getSentimentColor('positive')).toBe('text-bullish');
  });

  it('returns bearish color for negative sentiment', () => {
    expect(getSentimentColor('negative')).toBe('text-bearish');
  });

  it('returns muted color for neutral sentiment', () => {
    expect(getSentimentColor('neutral')).toBe('text-muted-foreground');
  });

  it('handles undefined', () => {
    expect(getSentimentColor(undefined)).toBe('text-muted-foreground');
  });
});

describe('getDirectionIcon', () => {
  it('returns up arrow for bullish', () => {
    expect(getDirectionIcon('BULLISH')).toBe('\u2191');
  });

  it('returns down arrow for bearish', () => {
    expect(getDirectionIcon('BEARISH')).toBe('\u2193');
  });

  it('returns right arrow for neutral', () => {
    expect(getDirectionIcon('NEUTRAL')).toBe('\u2192');
  });

  it('returns right arrow for undefined', () => {
    expect(getDirectionIcon(undefined)).toBe('\u2192');
  });
});

describe('getUrgencyColor', () => {
  it('returns red for critical', () => {
    expect(getUrgencyColor('CRITICAL')).toBe('bg-red-500');
  });

  it('returns orange for high', () => {
    expect(getUrgencyColor('HIGH')).toBe('bg-orange-500');
  });

  it('returns yellow for medium', () => {
    expect(getUrgencyColor('MEDIUM')).toBe('bg-yellow-500');
  });

  it('returns gray for low', () => {
    expect(getUrgencyColor('LOW')).toBe('bg-gray-400');
  });

  it('returns light gray for undefined', () => {
    expect(getUrgencyColor(undefined)).toBe('bg-gray-300');
  });
});

describe('truncate', () => {
  it('truncates long strings', () => {
    expect(truncate('Hello World', 5)).toBe('Hello...');
  });

  it('does not truncate short strings', () => {
    expect(truncate('Hello', 10)).toBe('Hello');
  });

  it('handles exact length', () => {
    expect(truncate('Hello', 5)).toBe('Hello');
  });

  it('handles empty string', () => {
    expect(truncate('', 10)).toBe('');
  });
});

describe('formatCurrency', () => {
  it('formats as USD currency', () => {
    expect(formatCurrency(1000)).toBe('$1,000');
    expect(formatCurrency(1000000)).toBe('$1,000,000');
  });

  it('handles zero', () => {
    expect(formatCurrency(0)).toBe('$0');
  });

  it('rounds to whole numbers', () => {
    expect(formatCurrency(1234.56)).toBe('$1,235');
  });
});

describe('formatNumber', () => {
  it('formats millions with M suffix', () => {
    expect(formatNumber(1500000)).toBe('1.5M');
    expect(formatNumber(1000000)).toBe('1.0M');
  });

  it('formats thousands with K suffix', () => {
    expect(formatNumber(1500)).toBe('1.5K');
    expect(formatNumber(1000)).toBe('1.0K');
  });

  it('does not format small numbers', () => {
    expect(formatNumber(500)).toBe('500');
    expect(formatNumber(0)).toBe('0');
  });
});

describe('debounce', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('delays function execution', () => {
    const mockFn = jest.fn();
    const debouncedFn = debounce(mockFn, 100);

    debouncedFn('test');
    expect(mockFn).not.toHaveBeenCalled();

    jest.advanceTimersByTime(100);
    expect(mockFn).toHaveBeenCalledWith('test');
  });

  it('only calls function once for rapid calls', () => {
    const mockFn = jest.fn();
    const debouncedFn = debounce(mockFn, 100);

    debouncedFn('first');
    debouncedFn('second');
    debouncedFn('third');

    jest.advanceTimersByTime(100);

    expect(mockFn).toHaveBeenCalledTimes(1);
    expect(mockFn).toHaveBeenCalledWith('third');
  });

  it('resets timer on each call', () => {
    const mockFn = jest.fn();
    const debouncedFn = debounce(mockFn, 100);

    debouncedFn('test');
    jest.advanceTimersByTime(50);

    debouncedFn('test2');
    jest.advanceTimersByTime(50);

    expect(mockFn).not.toHaveBeenCalled();

    jest.advanceTimersByTime(50);
    expect(mockFn).toHaveBeenCalledWith('test2');
  });
});
