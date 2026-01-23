'use client';

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, CACHE_TIMES, QUERY_KEYS, ApiError } from '@/lib/api';
import type { Event, EventFilters, EventsResponse } from '@/types/events';
import type { User, WatchlistItem, Alert, AlertCreate } from '@/types/user';

/**
 * Custom hook options that extend React Query options
 */
interface UseApiQueryOptions<TData> {
  enabled?: boolean;
  refetchInterval?: number | false;
  onSuccess?: (data: TData) => void;
  onError?: (error: Error) => void;
  showErrorToast?: boolean;
}

/**
 * Handle API errors consistently
 */
function handleApiError(error: unknown, showToast = true): void {
  const message = error instanceof ApiError
    ? error.message
    : error instanceof Error
    ? error.message
    : 'An unexpected error occurred';

  console.error('API Error:', error);

  if (showToast) {
    toast.error(message);
  }
}

// ============================================================================
// Event Hooks
// ============================================================================

/**
 * Fetch events with filtering and pagination
 */
export function useEvents(
  params: EventFilters & { page?: number; page_size?: number } = {},
  options: UseApiQueryOptions<EventsResponse> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.events(params),
    queryFn: () => api.getEvents(params),
    staleTime: CACHE_TIMES.events,
    gcTime: CACHE_TIMES.events * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch latest events
 */
export function useLatestEvents(
  limit: number = 50,
  options: UseApiQueryOptions<Event[]> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.latestEvents(limit),
    queryFn: () => api.getLatestEvents(limit),
    staleTime: CACHE_TIMES.latestEvents,
    gcTime: CACHE_TIMES.latestEvents * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch high alpha events
 */
export function useHighAlphaEvents(
  minScore: number = 0.5,
  limit: number = 20,
  options: UseApiQueryOptions<Event[]> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.highAlphaEvents(minScore, limit),
    queryFn: () => api.getHighAlphaEvents(minScore, limit),
    staleTime: CACHE_TIMES.highAlphaEvents,
    gcTime: CACHE_TIMES.highAlphaEvents * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch events for a specific ticker
 */
export function useTickerEvents(
  ticker: string,
  limit: number = 50,
  options: UseApiQueryOptions<Event[]> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.tickerEvents(ticker, limit),
    queryFn: () => api.getTickerEvents(ticker, limit),
    staleTime: CACHE_TIMES.tickerEvents,
    gcTime: CACHE_TIMES.tickerEvents * 2,
    enabled: !!ticker,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch a single event by ID
 */
export function useEvent(
  id: string,
  options: UseApiQueryOptions<Event> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.event(id),
    queryFn: () => api.getEvent(id),
    staleTime: CACHE_TIMES.events,
    gcTime: CACHE_TIMES.events * 2,
    enabled: !!id,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch dashboard stats
 */
export function useStats(options: UseApiQueryOptions<{
  total_events: number;
  total_events_yesterday: number;
  bullish_events: number;
  bullish_events_yesterday: number;
  bearish_events: number;
  bearish_events_yesterday: number;
  high_alpha_events: number;
  high_alpha_events_last_hour: number;
}> = {}) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.stats(),
    queryFn: () => api.getStats(),
    staleTime: CACHE_TIMES.stats,
    gcTime: CACHE_TIMES.stats * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

// ============================================================================
// Ticker Hooks
// ============================================================================

/**
 * Fetch all tickers
 */
export function useTickers(options: UseApiQueryOptions<string[]> = {}) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.tickers(),
    queryFn: () => api.getTickers(),
    staleTime: CACHE_TIMES.tickers,
    gcTime: CACHE_TIMES.tickers * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch ticker info
 */
export function useTickerInfo(
  ticker: string,
  options: UseApiQueryOptions<{
    ticker: string;
    event_count: number;
    avg_sentiment: number;
    latest_event?: Event;
  }> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.tickerInfo(ticker),
    queryFn: () => api.getTickerInfo(ticker),
    staleTime: CACHE_TIMES.tickerInfo,
    gcTime: CACHE_TIMES.tickerInfo * 2,
    enabled: !!ticker,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch ticker sentiment
 */
export function useTickerSentiment(
  ticker: string,
  hours: number = 24,
  options: UseApiQueryOptions<{
    ticker: string;
    avg_sentiment: number;
    event_count: number;
    sentiment_trend: 'improving' | 'declining' | 'stable';
  }> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.tickerSentiment(ticker, hours),
    queryFn: () => api.getTickerSentiment(ticker, hours),
    staleTime: CACHE_TIMES.tickerSentiment,
    gcTime: CACHE_TIMES.tickerSentiment * 2,
    enabled: !!ticker,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch ticker stats
 */
export function useTickerStats(
  ticker: string,
  hours: number = 24,
  options: UseApiQueryOptions<{
    ticker: string;
    event_count: number;
    avg_sentiment: number;
    avg_alpha: number;
    bullish_count: number;
    bearish_count: number;
    neutral_count: number;
    high_alpha_count: number;
    sentiment_trend: 'improving' | 'declining' | 'stable';
    last_event_time: string | null;
    time_window_hours: number;
  }> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.tickerStats(ticker, hours),
    queryFn: () => api.getTickerStats(ticker, hours),
    staleTime: CACHE_TIMES.tickerStats,
    gcTime: CACHE_TIMES.tickerStats * 2,
    enabled: !!ticker,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch ticker price
 */
export function useTickerPrice(
  ticker: string,
  options: UseApiQueryOptions<{
    ticker: string;
    price: number | null;
    change: number | null;
    change_percent: number | null;
    volume: number | null;
    market_cap: number | null;
    high_52w: number | null;
    low_52w: number | null;
    last_updated: string | null;
    source: string;
  }> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.tickerPrice(ticker),
    queryFn: () => api.getTickerPrice(ticker),
    staleTime: CACHE_TIMES.tickerPrice,
    gcTime: CACHE_TIMES.tickerPrice * 2,
    enabled: !!ticker,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch related tickers
 */
export function useRelatedTickers(
  ticker: string,
  limit: number = 10,
  options: UseApiQueryOptions<{
    ticker: string;
    related: Array<{
      ticker: string;
      company_name: string | null;
      reason: string;
      event_count: number;
      avg_sentiment: number;
    }>;
  }> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.relatedTickers(ticker, limit),
    queryFn: () => api.getRelatedTickers(ticker, limit),
    staleTime: CACHE_TIMES.relatedTickers,
    gcTime: CACHE_TIMES.relatedTickers * 2,
    enabled: !!ticker,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

// ============================================================================
// Search Hooks
// ============================================================================

/**
 * Search events
 */
export function useSearch(
  query: string,
  filters: EventFilters = {},
  options: UseApiQueryOptions<EventsResponse> = {}
) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.search(query, filters),
    queryFn: () => api.search(query, filters),
    staleTime: CACHE_TIMES.search,
    gcTime: CACHE_TIMES.search * 2,
    enabled: !!query && query.length > 0,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

// ============================================================================
// Watchlist Hooks
// ============================================================================

/**
 * Fetch user watchlist
 */
export function useWatchlist(options: UseApiQueryOptions<WatchlistItem[]> = {}) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.watchlist(),
    queryFn: () => api.getWatchlist(),
    staleTime: CACHE_TIMES.watchlist,
    gcTime: CACHE_TIMES.watchlist * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Add to watchlist mutation
 */
export function useAddToWatchlist(options: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
} = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticker, notes }: { ticker: string; notes?: string }) =>
      api.addToWatchlist(ticker, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.watchlist() });
      toast.success('Added to watchlist');
      options.onSuccess?.();
    },
    onError: (error: Error) => {
      handleApiError(error);
      options.onError?.(error);
    },
  });
}

/**
 * Remove from watchlist mutation
 */
export function useRemoveFromWatchlist(options: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
} = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ticker: string) => api.removeFromWatchlist(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.watchlist() });
      toast.success('Removed from watchlist');
      options.onSuccess?.();
    },
    onError: (error: Error) => {
      handleApiError(error);
      options.onError?.(error);
    },
  });
}

// ============================================================================
// Alert Hooks
// ============================================================================

/**
 * Fetch user alerts
 */
export function useAlerts(options: UseApiQueryOptions<Alert[]> = {}) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.alerts(),
    queryFn: () => api.getAlerts(),
    staleTime: CACHE_TIMES.alerts,
    gcTime: CACHE_TIMES.alerts * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Create alert mutation
 */
export function useCreateAlert(options: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
} = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AlertCreate) => api.createAlert(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.alerts() });
      toast.success('Alert created');
      options.onSuccess?.();
    },
    onError: (error: Error) => {
      handleApiError(error);
      options.onError?.(error);
    },
  });
}

/**
 * Update alert mutation
 */
export function useUpdateAlert(options: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
} = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AlertCreate & { is_active: boolean }> }) =>
      api.updateAlert(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.alerts() });
      toast.success('Alert updated');
      options.onSuccess?.();
    },
    onError: (error: Error) => {
      handleApiError(error);
      options.onError?.(error);
    },
  });
}

/**
 * Delete alert mutation
 */
export function useDeleteAlert(options: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
} = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.alerts() });
      toast.success('Alert deleted');
      options.onSuccess?.();
    },
    onError: (error: Error) => {
      handleApiError(error);
      options.onError?.(error);
    },
  });
}

// ============================================================================
// User Hooks
// ============================================================================

/**
 * Fetch current user
 */
export function useCurrentUser(options: UseApiQueryOptions<User> = {}) {
  const { showErrorToast = false, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.currentUser(),
    queryFn: () => api.getCurrentUser(),
    staleTime: CACHE_TIMES.currentUser,
    gcTime: CACHE_TIMES.currentUser * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Fetch subscription
 */
export function useSubscription(options: UseApiQueryOptions<{
  tier: string;
  status: string;
  stripe_customer_id?: string;
  stripe_subscription_id?: string;
}> = {}) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.subscription(),
    queryFn: () => api.getSubscription(),
    staleTime: CACHE_TIMES.subscription,
    gcTime: CACHE_TIMES.subscription * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

// ============================================================================
// Notification Hooks
// ============================================================================

/**
 * Fetch notification preferences
 */
export function useNotificationPreferences(options: UseApiQueryOptions<{
  push_enabled: boolean;
  realtime_alerts: boolean;
  high_alpha_signals: boolean;
  email_alerts: boolean;
  daily_digest: boolean;
  weekly_report: boolean;
  product_updates: boolean;
  min_alpha_score: number;
}> = {}) {
  const { showErrorToast = true, ...queryOptions } = options;

  return useQuery({
    queryKey: QUERY_KEYS.notificationPreferences(),
    queryFn: () => api.getNotificationPreferences(),
    staleTime: CACHE_TIMES.notificationPreferences,
    gcTime: CACHE_TIMES.notificationPreferences * 2,
    ...queryOptions,
    meta: {
      onError: (error: Error) => handleApiError(error, showErrorToast),
    },
  });
}

/**
 * Update notification preferences mutation
 */
export function useUpdateNotificationPreferences(options: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
} = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (preferences: {
      pushEnabled?: boolean;
      realtimeAlerts?: boolean;
      highAlphaSignals?: boolean;
      emailAlerts?: boolean;
      dailyDigest?: boolean;
      weeklyReport?: boolean;
      productUpdates?: boolean;
      minAlphaScore?: number;
    }) => api.updateNotificationPreferences(preferences),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.notificationPreferences() });
      toast.success('Notification preferences updated');
      options.onSuccess?.();
    },
    onError: (error: Error) => {
      handleApiError(error);
      options.onError?.(error);
    },
  });
}

/**
 * Register FCM token mutation
 */
export function useRegisterFCMToken(options: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
} = {}) {
  return useMutation({
    mutationFn: ({ token, deviceInfo }: { token: string; deviceInfo?: { platform?: string; browser?: string } }) =>
      api.registerFCMToken(token, deviceInfo),
    onSuccess: () => {
      options.onSuccess?.();
    },
    onError: (error: Error) => {
      // Don't show toast for FCM registration failures - usually not critical
      console.error('FCM registration failed:', error);
      options.onError?.(error);
    },
  });
}

// ============================================================================
// Cache Invalidation Utilities
// ============================================================================

/**
 * Hook to get cache invalidation functions
 */
export function useCacheInvalidation() {
  const queryClient = useQueryClient();

  return {
    /**
     * Invalidate all event-related queries
     */
    invalidateEvents: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },

    /**
     * Invalidate all ticker-related queries
     */
    invalidateTickers: () => {
      queryClient.invalidateQueries({ queryKey: ['tickers'] });
    },

    /**
     * Invalidate watchlist
     */
    invalidateWatchlist: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.watchlist() });
    },

    /**
     * Invalidate alerts
     */
    invalidateAlerts: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.alerts() });
    },

    /**
     * Invalidate user data
     */
    invalidateUser: () => {
      queryClient.invalidateQueries({ queryKey: ['user'] });
      queryClient.invalidateQueries({ queryKey: ['billing'] });
    },

    /**
     * Invalidate notification preferences
     */
    invalidateNotifications: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },

    /**
     * Invalidate all queries
     */
    invalidateAll: () => {
      queryClient.invalidateQueries();
    },

    /**
     * Clear all cached data
     */
    clearCache: () => {
      queryClient.clear();
    },
  };
}
