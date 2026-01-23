import { getSession } from 'next-auth/react';
import type { Event, EventFilters, EventsResponse } from '@/types/events';
import type { User, WatchlistItem, Alert, AlertCreate } from '@/types/user';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Auth mock mode - allows any credentials for login
const AUTH_MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

// Retry configuration
const RETRY_CONFIG = {
  maxRetries: 3,
  baseDelayMs: 1000, // 1 second base delay
  maxDelayMs: 10000, // 10 second max delay
};

// Cache time configuration (in milliseconds) for different endpoint types
export const CACHE_TIMES = {
  // Real-time data - short cache
  events: 30 * 1000, // 30 seconds
  latestEvents: 30 * 1000, // 30 seconds
  highAlphaEvents: 30 * 1000, // 30 seconds
  tickerEvents: 30 * 1000, // 30 seconds
  stats: 60 * 1000, // 1 minute

  // Semi-static data - medium cache
  tickers: 5 * 60 * 1000, // 5 minutes
  tickerInfo: 2 * 60 * 1000, // 2 minutes
  tickerSentiment: 2 * 60 * 1000, // 2 minutes
  tickerStats: 2 * 60 * 1000, // 2 minutes
  tickerPrice: 60 * 1000, // 1 minute (prices change frequently)
  relatedTickers: 10 * 60 * 1000, // 10 minutes (relatively static)
  search: 60 * 1000, // 1 minute

  // User data - short cache with mutation invalidation
  watchlist: 60 * 1000, // 1 minute
  alerts: 60 * 1000, // 1 minute
  currentUser: 5 * 60 * 1000, // 5 minutes
  subscription: 5 * 60 * 1000, // 5 minutes
  notificationPreferences: 5 * 60 * 1000, // 5 minutes
} as const;

// Query keys for consistent cache management
export const QUERY_KEYS = {
  events: (filters?: EventFilters) => ['events', filters] as const,
  latestEvents: (limit?: number) => ['events', 'latest', limit] as const,
  highAlphaEvents: (minScore?: number, limit?: number) => ['events', 'high-alpha', minScore, limit] as const,
  tickerEvents: (ticker: string, limit?: number) => ['events', 'ticker', ticker, limit] as const,
  event: (id: string) => ['events', id] as const,
  stats: () => ['stats'] as const,
  tickers: () => ['tickers'] as const,
  tickerInfo: (ticker: string) => ['tickers', ticker, 'info'] as const,
  tickerSentiment: (ticker: string, hours?: number) => ['tickers', ticker, 'sentiment', hours] as const,
  tickerStats: (ticker: string, hours?: number) => ['tickers', ticker, 'stats', hours] as const,
  tickerPrice: (ticker: string) => ['tickers', ticker, 'price'] as const,
  relatedTickers: (ticker: string, limit?: number) => ['tickers', ticker, 'related', limit] as const,
  search: (query: string, filters?: EventFilters) => ['search', query, filters] as const,
  watchlist: () => ['watchlist'] as const,
  alerts: () => ['alerts'] as const,
  currentUser: () => ['user', 'current'] as const,
  subscription: () => ['billing', 'subscription'] as const,
  notificationPreferences: () => ['notifications', 'preferences'] as const,
} as const;

/**
 * Custom API error with status code and response data
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /**
   * Check if error is a client error (4xx) that should not be retried
   */
  isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }

  /**
   * Check if error is a server error (5xx) that may be retried
   */
  isServerError(): boolean {
    return this.status >= 500;
  }
}

/**
 * Calculate delay for exponential backoff
 */
function calculateBackoffDelay(attempt: number): number {
  // Exponential backoff: 1s, 2s, 4s, 8s... capped at maxDelayMs
  const delay = RETRY_CONFIG.baseDelayMs * Math.pow(2, attempt);
  return Math.min(delay, RETRY_CONFIG.maxDelayMs);
}

/**
 * Wait for specified milliseconds
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Check if an error is retryable
 */
function isRetryableError(error: unknown): boolean {
  // Network errors are retryable
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return true;
  }

  // Only retry server errors (5xx), not client errors (4xx)
  if (error instanceof ApiError) {
    return error.isServerError();
  }

  return false;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async getHeaders(): Promise<HeadersInit> {
    const session = await getSession();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (session?.accessToken) {
      headers['Authorization'] = `Bearer ${session.accessToken}`;
    }

    return headers;
  }

  /**
   * Make a request with automatic retry logic
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers = await this.getHeaders();
    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= RETRY_CONFIG.maxRetries; attempt++) {
      try {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
          ...options,
          headers: {
            ...headers,
            ...options.headers,
          },
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          const errorMessage = errorData.detail || `API error: ${response.status}`;
          throw new ApiError(errorMessage, response.status, errorData);
        }

        return response.json();
      } catch (error) {
        lastError = error as Error;

        // Don't retry if this is the last attempt or error is not retryable
        if (attempt >= RETRY_CONFIG.maxRetries || !isRetryableError(error)) {
          break;
        }

        // Calculate backoff delay and wait before retrying
        const delay = calculateBackoffDelay(attempt);
        console.warn(
          `API request failed (attempt ${attempt + 1}/${RETRY_CONFIG.maxRetries + 1}), ` +
          `retrying in ${delay}ms...`,
          endpoint
        );
        await sleep(delay);
      }
    }

    // Throw the last error after all retries exhausted
    throw lastError;
  }

  // Auth endpoints
  async login(email: string, password: string) {
    if (AUTH_MOCK_MODE) {
      return { access_token: 'mock-token', token_type: 'bearer' };
    }
    return this.request<{ access_token: string; token_type: string }>(
      '/api/v1/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }
    );
  }

  async register(email: string, password: string, full_name?: string) {
    if (AUTH_MOCK_MODE) {
      return {
        id: 'mock-user-' + Date.now(),
        email,
        full_name: full_name || email.split('@')[0],
        subscription_tier: 'starter',
      } as User;
    }
    return this.request<User>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    });
  }

  async getCurrentUser() {
    if (AUTH_MOCK_MODE) {
      return {
        id: 'mock-user-123',
        email: 'demo@micro-alpha.com',
        full_name: 'Demo User',
        subscription_tier: 'professional',
      } as User;
    }
    return this.request<User>('/api/v1/auth/me');
  }

  // Events endpoints
  async getEvents(params: EventFilters & { page?: number; page_size?: number } = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });

    return this.request<EventsResponse>(
      `/api/v1/events?${searchParams.toString()}`
    );
  }

  async getEvent(id: string) {
    return this.request<Event>(`/api/v1/events/${id}`);
  }

  async getLatestEvents(limit: number = 50) {
    return this.request<Event[]>(`/api/v1/events/latest?limit=${limit}`);
  }

  async getHighAlphaEvents(min_score: number = 0.5, limit: number = 20) {
    return this.request<Event[]>(
      `/api/v1/events/high-alpha?min_score=${min_score}&limit=${limit}`
    );
  }

  async getTickerEvents(ticker: string, limit: number = 50) {
    return this.request<Event[]>(
      `/api/v1/events/ticker/${ticker}?limit=${limit}`
    );
  }

  // Search endpoints
  async search(query: string, filters: EventFilters = {}) {
    return this.request<EventsResponse>('/api/v1/search', {
      method: 'POST',
      body: JSON.stringify({ query, ...filters }),
    });
  }

  // Ticker endpoints
  async getTickers() {
    return this.request<string[]>('/api/v1/tickers');
  }

  async getTickerInfo(ticker: string) {
    return this.request<{
      ticker: string;
      event_count: number;
      avg_sentiment: number;
      latest_event?: Event;
    }>(`/api/v1/tickers/${ticker}`);
  }

  async getTickerSentiment(ticker: string, hours: number = 24) {
    return this.request<{
      ticker: string;
      avg_sentiment: number;
      event_count: number;
      sentiment_trend: 'improving' | 'declining' | 'stable';
    }>(`/api/v1/tickers/${ticker}/sentiment?hours=${hours}`);
  }

  async getTickerStats(ticker: string, hours: number = 24) {
    return this.request<{
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
    }>(`/api/v1/tickers/${ticker}/stats?hours=${hours}`);
  }

  async getTickerPrice(ticker: string) {
    return this.request<{
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
    }>(`/api/v1/tickers/${ticker}/price`);
  }

  async getRelatedTickers(ticker: string, limit: number = 10) {
    return this.request<{
      ticker: string;
      related: Array<{
        ticker: string;
        company_name: string | null;
        reason: string;
        event_count: number;
        avg_sentiment: number;
      }>;
    }>(`/api/v1/tickers/${ticker}/related?limit=${limit}`);
  }

  // Watchlist endpoints
  async getWatchlist() {
    return this.request<WatchlistItem[]>('/api/v1/watchlist');
  }

  async addToWatchlist(ticker: string, notes?: string) {
    return this.request<WatchlistItem>('/api/v1/watchlist', {
      method: 'POST',
      body: JSON.stringify({ ticker, notes }),
    });
  }

  async removeFromWatchlist(ticker: string) {
    return this.request<{ status: string }>(`/api/v1/watchlist/${ticker}`, {
      method: 'DELETE',
    });
  }

  // Alerts endpoints
  async getAlerts() {
    return this.request<Alert[]>('/api/v1/alerts');
  }

  async createAlert(data: AlertCreate) {
    return this.request<Alert>('/api/v1/alerts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateAlert(id: string, data: Partial<AlertCreate & { is_active: boolean }>) {
    return this.request<Alert>(`/api/v1/alerts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteAlert(id: string) {
    return this.request<{ status: string }>(`/api/v1/alerts/${id}`, {
      method: 'DELETE',
    });
  }

  // Billing endpoints
  async getSubscription() {
    return this.request<{
      tier: string;
      status: string;
      stripe_customer_id?: string;
      stripe_subscription_id?: string;
    }>('/api/v1/billing/subscription');
  }

  async createCheckoutSession(tier: string) {
    return this.request<{ session_id: string; url: string }>(
      `/api/v1/billing/checkout?tier=${tier}`,
      { method: 'POST' }
    );
  }

  async createPortalSession() {
    return this.request<{ url: string }>('/api/v1/billing/portal', {
      method: 'POST',
    });
  }

  // Stats endpoint
  async getStats() {
    return this.request<{
      total_events: number;
      total_events_yesterday: number;
      bullish_events: number;
      bullish_events_yesterday: number;
      bearish_events: number;
      bearish_events_yesterday: number;
      high_alpha_events: number;
      high_alpha_events_last_hour: number;
    }>('/api/v1/stats');
  }

  // FCM Token endpoints
  async registerFCMToken(token: string, deviceInfo?: { platform?: string; browser?: string }) {
    return this.request<{ status: string }>('/api/v1/notifications/fcm/register', {
      method: 'POST',
      body: JSON.stringify({ token, device_info: deviceInfo }),
    });
  }

  async unregisterFCMToken(token: string) {
    return this.request<{ status: string }>('/api/v1/notifications/fcm/unregister', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  }

  // Notification preferences endpoints
  async getNotificationPreferences() {
    return this.request<{
      push_enabled: boolean;
      realtime_alerts: boolean;
      high_alpha_signals: boolean;
      email_alerts: boolean;
      daily_digest: boolean;
      weekly_report: boolean;
      product_updates: boolean;
      min_alpha_score: number;
    }>('/api/v1/notifications/preferences');
  }

  async updateNotificationPreferences(preferences: {
    pushEnabled?: boolean;
    realtimeAlerts?: boolean;
    highAlphaSignals?: boolean;
    emailAlerts?: boolean;
    dailyDigest?: boolean;
    weeklyReport?: boolean;
    productUpdates?: boolean;
    minAlphaScore?: number;
  }) {
    // Convert camelCase to snake_case for backend
    const payload = {
      push_enabled: preferences.pushEnabled,
      realtime_alerts: preferences.realtimeAlerts,
      high_alpha_signals: preferences.highAlphaSignals,
      email_alerts: preferences.emailAlerts,
      daily_digest: preferences.dailyDigest,
      weekly_report: preferences.weeklyReport,
      product_updates: preferences.productUpdates,
      min_alpha_score: preferences.minAlphaScore,
    };

    return this.request<{ status: string }>('/api/v1/notifications/preferences', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  // Test push notification (for development)
  async sendTestNotification() {
    return this.request<{ status: string }>('/api/v1/notifications/test', {
      method: 'POST',
    });
  }
}

export const api = new ApiClient(API_URL);
