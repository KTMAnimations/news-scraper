'use client';

import { useQuery } from '@tanstack/react-query';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  DollarSign,
  BarChart2,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PriceDisplayProps {
  ticker: string;
}

function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '-';
  if (num >= 1_000_000_000) return `${(num / 1_000_000_000).toFixed(2)}B`;
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(2)}K`;
  return num.toLocaleString();
}

function formatPrice(price: number | null | undefined): string {
  if (price === null || price === undefined) return '-';
  return price.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function PriceDisplay({ ticker }: PriceDisplayProps) {
  const { data: priceData, isLoading, error } = useQuery({
    queryKey: ['ticker-price', ticker],
    queryFn: () => api.getTickerPrice(ticker),
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 15000, // Consider stale after 15 seconds
  });

  if (isLoading) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Price</h3>
        <div className="space-y-3">
          <div className="skeleton h-10 w-32 rounded" />
          <div className="skeleton h-6 w-24 rounded" />
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div className="skeleton h-12 rounded" />
            <div className="skeleton h-12 rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !priceData) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Price</h3>
        <div className="flex items-center gap-2 text-text-tertiary">
          <AlertCircle className="h-4 w-4" />
          <p className="text-sm">Unable to load price data</p>
        </div>
      </div>
    );
  }

  // Check if we have valid price data
  const hasPrice = priceData.price !== null;

  if (!hasPrice) {
    return (
      <div className="card rounded-2xl p-5">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Price</h3>
        <div className="flex items-center gap-2 text-text-tertiary">
          <AlertCircle className="h-4 w-4" />
          <p className="text-sm">Price data unavailable for {ticker}</p>
        </div>
      </div>
    );
  }

  const isPositive = priceData.change !== null && priceData.change > 0;
  const isNegative = priceData.change !== null && priceData.change < 0;

  const ChangeIcon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
  const changeColor = isPositive ? 'text-positive' : isNegative ? 'text-negative' : 'text-text-tertiary';
  const changeBg = isPositive ? 'bg-positive-subtle' : isNegative ? 'bg-negative-subtle' : 'bg-bg-tertiary';

  return (
    <div className="card rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-text-primary">Price</h3>
        {priceData.source !== 'none' && (
          <span className="text-xs text-text-quaternary">
            via {priceData.source}
          </span>
        )}
      </div>

      {/* Current Price */}
      <div className="mb-4">
        <p className="font-mono text-4xl font-bold text-text-primary">
          {formatPrice(priceData.price)}
        </p>

        {/* Change */}
        {priceData.change !== null && (
          <div className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg mt-2',
            changeBg
          )}>
            <ChangeIcon className={cn('h-4 w-4', changeColor)} />
            <span className={cn('font-mono font-medium', changeColor)}>
              {isPositive ? '+' : ''}{formatPrice(priceData.change)}
            </span>
            {priceData.change_percent !== null && (
              <span className={cn('font-mono text-sm', changeColor)}>
                ({isPositive ? '+' : ''}{priceData.change_percent?.toFixed(2)}%)
              </span>
            )}
          </div>
        )}
      </div>

      {/* Additional Info */}
      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
        {/* Volume */}
        {priceData.volume !== null && (
          <div>
            <div className="flex items-center gap-1.5 text-text-tertiary mb-1">
              <BarChart2 className="h-3.5 w-3.5" />
              <span className="text-xs">Volume</span>
            </div>
            <p className="font-mono text-lg font-semibold text-text-primary">
              {formatNumber(priceData.volume)}
            </p>
          </div>
        )}

        {/* Market Cap */}
        {priceData.market_cap !== null && (
          <div>
            <div className="flex items-center gap-1.5 text-text-tertiary mb-1">
              <DollarSign className="h-3.5 w-3.5" />
              <span className="text-xs">Market Cap</span>
            </div>
            <p className="font-mono text-lg font-semibold text-text-primary">
              {formatNumber(priceData.market_cap)}
            </p>
          </div>
        )}
      </div>

      {/* 52 Week Range */}
      {(priceData.low_52w !== null || priceData.high_52w !== null) && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-xs text-text-tertiary mb-2">52 Week Range</p>
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm text-text-secondary">
              {formatPrice(priceData.low_52w)}
            </span>
            <div className="flex-1 h-2 bg-bg-tertiary rounded-full relative">
              {priceData.price !== null && priceData.low_52w !== null && priceData.high_52w !== null && (
                <div
                  className="absolute h-2 w-2 bg-accent rounded-full top-0 transform -translate-x-1/2"
                  style={{
                    left: `${Math.min(100, Math.max(0,
                      ((priceData.price - priceData.low_52w) /
                        (priceData.high_52w - priceData.low_52w)) * 100
                    ))}%`
                  }}
                />
              )}
            </div>
            <span className="font-mono text-sm text-text-secondary">
              {formatPrice(priceData.high_52w)}
            </span>
          </div>
        </div>
      )}

      {/* Last Updated */}
      {priceData.last_updated && (
        <div className="mt-4 flex items-center gap-1.5 text-xs text-text-quaternary">
          <Clock className="h-3 w-3" />
          <span>
            Updated {new Date(priceData.last_updated).toLocaleTimeString()}
          </span>
        </div>
      )}
    </div>
  );
}
