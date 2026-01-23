import { getSession } from 'next-auth/react';
import type { Event, EventFilters, EventsResponse } from '@/types/events';
import type { User, WatchlistItem, Alert, AlertCreate } from '@/types/user';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

// Mock data for development/testing
const mockEvents: Event[] = [
  {
    id: '1',
    ticker: 'ABCD',
    event_time: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'INSIDER_BUY',
    event_category: 'SEC_FILING',
    headline: 'CEO purchases 50,000 shares at $2.15 in open market transaction',
    summary: 'The CEO has made a significant open market purchase, signaling strong confidence in the company\'s future prospects.',
    source_name: 'SEC EDGAR',
    source_url: 'https://sec.gov/cgi-bin/browse-edgar',
    sentiment_score: 0.85,
    sentiment_label: 'positive',
    sentiment_confidence: 0.92,
	    alpha_score: 0.78,
	    direction: 'BULLISH',
	    urgency: 'HIGH',
	    extracted_tickers: ['ABCD'],
	    extracted_companies: ['ABCD Corp'],
	    extracted_people: ['John Smith'],
	  },
  {
    id: '2',
    ticker: 'EFGH',
    event_time: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'EARNINGS_MISS',
    event_category: 'EARNINGS',
    headline: 'Q4 earnings miss expectations, revenue down 12% YoY',
    summary: 'The company reported disappointing Q4 results with revenue and earnings both missing analyst estimates.',
    source_name: 'PR Newswire',
    sentiment_score: -0.72,
    sentiment_label: 'negative',
    sentiment_confidence: 0.88,
	    alpha_score: -0.65,
	    direction: 'BEARISH',
	    urgency: 'HIGH',
	    extracted_tickers: ['EFGH'],
	  },
  {
    id: '3',
    ticker: 'IJKL',
    event_time: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'FDA_APPROVAL',
    event_category: 'REGULATORY',
    headline: 'FDA grants breakthrough therapy designation for lead drug candidate',
    summary: 'The FDA has granted breakthrough therapy designation, which could accelerate the approval timeline significantly.',
    source_name: 'FDA',
    sentiment_score: 0.95,
    sentiment_label: 'positive',
    sentiment_confidence: 0.96,
	    alpha_score: 0.92,
	    direction: 'BULLISH',
	    urgency: 'CRITICAL',
	    extracted_tickers: ['IJKL'],
	  },
  {
    id: '4',
    ticker: 'MNOP',
    event_time: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'ACTIVIST_STAKE',
    event_category: 'SEC_FILING',
    headline: 'Activist fund discloses 8.5% stake, plans to push for strategic review',
    summary: 'A well-known activist investor has acquired a significant stake and is pushing for changes.',
    source_name: 'SEC EDGAR',
    sentiment_score: 0.45,
    sentiment_label: 'positive',
    sentiment_confidence: 0.75,
    alpha_score: 0.55,
    direction: 'BULLISH',
    extracted_tickers: ['MNOP'],
  },
  {
    id: '5',
    ticker: 'QRST',
    event_time: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'OFFERING',
    event_category: 'CAPITAL_MARKETS',
    headline: 'Company announces $15M registered direct offering at $1.50 per share',
    summary: 'Dilutive offering announced below current market price.',
    source_name: 'GlobeNewswire',
    sentiment_score: -0.55,
    sentiment_label: 'negative',
    sentiment_confidence: 0.82,
    alpha_score: -0.48,
    direction: 'BEARISH',
    extracted_tickers: ['QRST'],
  },
  {
    id: '6',
    ticker: 'UVWX',
    event_time: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'MANAGEMENT_CHANGE',
    event_category: 'CORPORATE',
    headline: 'CFO resigns unexpectedly, interim CFO appointed',
    summary: 'The company announced the sudden departure of its Chief Financial Officer.',
    source_name: 'Business Wire',
    sentiment_score: -0.35,
    sentiment_label: 'negative',
    sentiment_confidence: 0.70,
    alpha_score: -0.28,
    direction: 'BEARISH',
    extracted_tickers: ['UVWX'],
  },
  {
    id: '7',
    ticker: 'YZAB',
    event_time: new Date(Date.now() - 120 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'INSIDER_BUY',
    event_category: 'SEC_FILING',
    headline: 'Multiple insiders purchase shares worth $2.3M total',
    summary: 'Cluster buying activity observed from multiple company insiders.',
    source_name: 'SEC EDGAR',
    sentiment_score: 0.88,
    sentiment_label: 'positive',
    sentiment_confidence: 0.94,
    alpha_score: 0.85,
    direction: 'BULLISH',
    extracted_tickers: ['YZAB'],
  },
  {
    id: '8',
    ticker: 'CDEF',
    event_time: new Date(Date.now() - 150 * 60 * 1000).toISOString(),
    ingest_time: new Date().toISOString(),
    event_type: 'CONTRACT_WIN',
    event_category: 'BUSINESS',
    headline: 'Company wins $45M government contract for 3 years',
    summary: 'Significant contract win that could meaningfully impact revenue.',
    source_name: 'PR Newswire',
    sentiment_score: 0.75,
    sentiment_label: 'positive',
    sentiment_confidence: 0.88,
    alpha_score: 0.72,
    direction: 'BULLISH',
    extracted_tickers: ['CDEF'],
  },
];

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
    if (MOCK_MODE) {
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
    if (MOCK_MODE) {
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
    if (MOCK_MODE) {
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
    if (MOCK_MODE) {
      return {
        events: mockEvents,
        total: mockEvents.length,
        page: 1,
        page_size: 50,
      } as EventsResponse;
    }

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
    if (MOCK_MODE) {
      return mockEvents.find((e) => e.id === id) || mockEvents[0];
    }
    return this.request<Event>(`/api/v1/events/${id}`);
  }

  async getLatestEvents(limit: number = 50) {
    if (MOCK_MODE) {
      return mockEvents.slice(0, limit);
    }
    return this.request<Event[]>(`/api/v1/events/latest?limit=${limit}`);
  }

  async getHighAlphaEvents(min_score: number = 0.5, limit: number = 20) {
    if (MOCK_MODE) {
      return mockEvents
        .filter((e) => Math.abs(e.alpha_score || 0) >= min_score)
        .slice(0, limit);
    }
    return this.request<Event[]>(
      `/api/v1/events/high-alpha?min_score=${min_score}&limit=${limit}`
    );
  }

  async getTickerEvents(ticker: string, limit: number = 50) {
    if (MOCK_MODE) {
      return mockEvents.filter((e) => e.ticker === ticker).slice(0, limit);
    }
    return this.request<Event[]>(
      `/api/v1/events/ticker/${ticker}?limit=${limit}`
    );
  }

  // Search endpoints
  async search(query: string, filters: EventFilters = {}) {
    if (MOCK_MODE) {
      const filtered = mockEvents.filter(
        (e) =>
          e.headline.toLowerCase().includes(query.toLowerCase()) ||
          e.ticker.toLowerCase().includes(query.toLowerCase())
      );
      return {
        events: filtered,
        total: filtered.length,
        page: 1,
        page_size: 50,
      } as EventsResponse;
    }
    return this.request<EventsResponse>('/api/v1/search', {
      method: 'POST',
      body: JSON.stringify({ query, ...filters }),
    });
  }

	  // Ticker endpoints
	  async getTickers() {
	    if (MOCK_MODE) {
	      return Array.from(new Set(mockEvents.map((e) => e.ticker)));
	    }
	    return this.request<string[]>('/api/v1/tickers');
	  }

  async getTickerInfo(ticker: string) {
    if (MOCK_MODE) {
      const tickerEvents = mockEvents.filter((e) => e.ticker === ticker);
      return {
        ticker,
        event_count: tickerEvents.length,
        avg_sentiment: tickerEvents.reduce((sum, e) => sum + (e.sentiment_score || 0), 0) / (tickerEvents.length || 1),
        latest_event: tickerEvents[0],
      };
    }
    return this.request<{
      ticker: string;
      event_count: number;
      avg_sentiment: number;
      latest_event?: Event;
    }>(`/api/v1/tickers/${ticker}`);
  }

  async getTickerSentiment(ticker: string, hours: number = 24) {
    if (MOCK_MODE) {
      return {
        ticker,
        avg_sentiment: 0.45,
        event_count: 12,
        sentiment_trend: 'improving' as const,
      };
    }
    return this.request<{
      ticker: string;
      avg_sentiment: number;
      event_count: number;
      sentiment_trend: 'improving' | 'declining' | 'stable';
    }>(`/api/v1/tickers/${ticker}/sentiment?hours=${hours}`);
  }

  // Watchlist endpoints
  async getWatchlist() {
    if (MOCK_MODE) {
      return [
        { ticker: 'ABCD', notes: 'Watching for insider activity', added_at: new Date().toISOString() },
        { ticker: 'IJKL', notes: 'FDA catalyst upcoming', added_at: new Date().toISOString() },
      ] as WatchlistItem[];
    }
    return this.request<WatchlistItem[]>('/api/v1/watchlist');
  }

  async addToWatchlist(ticker: string, notes?: string) {
    if (MOCK_MODE) {
      return { ticker, notes, added_at: new Date().toISOString() } as WatchlistItem;
    }
    return this.request<WatchlistItem>('/api/v1/watchlist', {
      method: 'POST',
      body: JSON.stringify({ ticker, notes }),
    });
  }

  async removeFromWatchlist(ticker: string) {
    if (MOCK_MODE) {
      return { status: 'removed' };
    }
    return this.request<{ status: string }>(`/api/v1/watchlist/${ticker}`, {
      method: 'DELETE',
    });
  }

  // Alerts endpoints
  async getAlerts() {
    if (MOCK_MODE) {
      return [] as Alert[];
    }
    return this.request<Alert[]>('/api/v1/alerts');
  }

  async createAlert(data: AlertCreate) {
    if (MOCK_MODE) {
      return { id: 'mock-alert-1', ...data, is_active: true } as Alert;
    }
    return this.request<Alert>('/api/v1/alerts', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateAlert(id: string, data: Partial<AlertCreate & { is_active: boolean }>) {
    if (MOCK_MODE) {
      return { id, ...data } as Alert;
    }
    return this.request<Alert>(`/api/v1/alerts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteAlert(id: string) {
    if (MOCK_MODE) {
      return { status: 'deleted' };
    }
    return this.request<{ status: string }>(`/api/v1/alerts/${id}`, {
      method: 'DELETE',
    });
  }

  // Billing endpoints
  async getSubscription() {
    if (MOCK_MODE) {
      return {
        tier: 'professional',
        status: 'active',
      };
    }
    return this.request<{
      tier: string;
      status: string;
      stripe_customer_id?: string;
      stripe_subscription_id?: string;
    }>('/api/v1/billing/subscription');
  }

  async createCheckoutSession(tier: string) {
    if (MOCK_MODE) {
      return { session_id: 'mock-session', url: '/dashboard/settings/billing' };
    }
    return this.request<{ session_id: string; url: string }>(
      `/api/v1/billing/checkout?tier=${tier}`,
      { method: 'POST' }
    );
  }

  async createPortalSession() {
    if (MOCK_MODE) {
      return { url: '/dashboard/settings/billing' };
    }
    return this.request<{ url: string }>('/api/v1/billing/portal', {
      method: 'POST',
    });
  }

  // Stats endpoint
  async getStats() {
    if (MOCK_MODE) {
      // Calculate from mock events
      const now = Date.now();
      const today = mockEvents.filter(
        (e) => new Date(e.event_time).getTime() > now - 24 * 60 * 60 * 1000
      );
      return {
        total_events: today.length,
        total_events_yesterday: Math.floor(today.length * 0.9),
        bullish_events: today.filter((e) => e.direction === 'BULLISH').length,
        bullish_events_yesterday: Math.floor(
          today.filter((e) => e.direction === 'BULLISH').length * 0.92
        ),
        bearish_events: today.filter((e) => e.direction === 'BEARISH').length,
        bearish_events_yesterday: Math.floor(
          today.filter((e) => e.direction === 'BEARISH').length * 1.05
        ),
        high_alpha_events: today.filter(
          (e) => Math.abs(e.alpha_score || 0) >= 0.7
        ).length,
        high_alpha_events_last_hour: today.filter(
          (e) =>
            Math.abs(e.alpha_score || 0) >= 0.7 &&
            new Date(e.event_time).getTime() > now - 60 * 60 * 1000
        ).length,
      };
    }
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
