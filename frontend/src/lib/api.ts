import { getSession } from 'next-auth/react';
import type { Event, EventFilters, EventsResponse } from '@/types/events';
import type { User, WatchlistItem, Alert, AlertCreate } from '@/types/user';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Auth mock mode - allows any credentials for login
const AUTH_MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

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

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers = await this.getHeaders();

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
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
}

export const api = new ApiClient(API_URL);
