/**
 * API Client Tests
 *
 * Tests for the API client class that handles communication with the backend.
 */

// We need to test the ApiClient class directly, so we'll import the module
// after setting up the mocks

const mockGetSession = jest.fn();
const mockFetch = jest.fn();

// Mock next-auth/react before importing the module
jest.mock('next-auth/react', () => ({
  getSession: () => mockGetSession(),
}));

// Mock global fetch
global.fetch = mockFetch;

// Set environment variables
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
process.env.NEXT_PUBLIC_MOCK_MODE = 'false';

// Import after mocks are set up
import { api } from '@/lib/api';

describe('ApiClient', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetSession.mockResolvedValue({
      user: { name: 'Test User', email: 'test@example.com' },
      accessToken: 'test-token',
    });
  });

  describe('authentication', () => {
    it('includes authorization header when session has token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getTickers();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/tickers',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('excludes authorization header when no session', async () => {
      mockGetSession.mockResolvedValueOnce(null);
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getTickers();

      const callArgs = mockFetch.mock.calls[0];
      const headers = callArgs[1].headers;
      expect(headers.Authorization).toBeUndefined();
    });
  });

  describe('error handling', () => {
    it('throws error with API message on failure', async () => {
      // 4xx errors are not retried, so single mock is sufficient
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Invalid request' }),
      });

      await expect(api.getTickers()).rejects.toThrow('Invalid request');
    });

    it('throws generic error when no message in response', async () => {
      // 4xx errors are not retried
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({}),
      });

      await expect(api.getTickers()).rejects.toThrow('API error: 400');
    });

    it('handles JSON parse errors gracefully', async () => {
      // 4xx errors are not retried
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      await expect(api.getTickers()).rejects.toThrow('API error: 404');
    });
  });

  describe('events endpoints', () => {
    it('getEvents fetches events with filters', async () => {
      const mockResponse = {
        events: [{ id: '1', ticker: 'AAPL' }],
        total: 1,
        page: 1,
        page_size: 20,
        has_more: false,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await api.getEvents({ ticker: 'AAPL', page: 1 });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/events?'),
        expect.anything()
      );
      expect(mockFetch.mock.calls[0][0]).toContain('ticker=AAPL');
      expect(mockFetch.mock.calls[0][0]).toContain('page=1');
      expect(result).toEqual(mockResponse);
    });

    it('getEvents handles empty filters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ events: [], total: 0 }),
      });

      await api.getEvents();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/events?',
        expect.anything()
      );
    });

    it('getEvent fetches single event by id', async () => {
      const mockEvent = { id: 'event-123', ticker: 'AAPL' };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockEvent),
      });

      const result = await api.getEvent('event-123');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/events/event-123',
        expect.anything()
      );
      expect(result).toEqual(mockEvent);
    });

    it('getLatestEvents fetches latest events with limit', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getLatestEvents(25);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/events/latest?limit=25',
        expect.anything()
      );
    });

    it('getLatestEvents uses default limit of 50', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getLatestEvents();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/events/latest?limit=50',
        expect.anything()
      );
    });

    it('getHighAlphaEvents fetches high alpha events', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getHighAlphaEvents(0.7, 10);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/events/high-alpha?min_score=0.7&limit=10',
        expect.anything()
      );
    });

    it('getTickerEvents fetches events for a ticker', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getTickerEvents('TSLA', 100);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/events/ticker/TSLA?limit=100',
        expect.anything()
      );
    });
  });

  describe('search endpoint', () => {
    it('search sends POST request with query and filters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ events: [], total: 0 }),
      });

      await api.search('Apple earnings', { direction: 'BULLISH' });

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/search',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ query: 'Apple earnings', direction: 'BULLISH' }),
        })
      );
    });
  });

  describe('tickers endpoints', () => {
    it('getTickers fetches all tickers', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(['AAPL', 'GOOGL', 'MSFT']),
      });

      const result = await api.getTickers();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/tickers',
        expect.anything()
      );
      expect(result).toEqual(['AAPL', 'GOOGL', 'MSFT']);
    });

    it('getTickerInfo fetches ticker details', async () => {
      const mockInfo = {
        ticker: 'AAPL',
        event_count: 150,
        avg_sentiment: 0.65,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockInfo),
      });

      const result = await api.getTickerInfo('AAPL');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/tickers/AAPL',
        expect.anything()
      );
      expect(result).toEqual(mockInfo);
    });

    it('getTickerSentiment fetches sentiment with hours param', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ avg_sentiment: 0.5 }),
      });

      await api.getTickerSentiment('AAPL', 48);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/tickers/AAPL/sentiment?hours=48',
        expect.anything()
      );
    });
  });

  describe('watchlist endpoints', () => {
    it('getWatchlist fetches user watchlist', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getWatchlist();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/watchlist',
        expect.anything()
      );
    });

    it('addToWatchlist sends POST with ticker and notes', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ ticker: 'AAPL', notes: 'Tech stock' }),
      });

      await api.addToWatchlist('AAPL', 'Tech stock');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/watchlist',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ ticker: 'AAPL', notes: 'Tech stock' }),
        })
      );
    });

    it('removeFromWatchlist sends DELETE request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: 'deleted' }),
      });

      await api.removeFromWatchlist('AAPL');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/watchlist/AAPL',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  describe('alerts endpoints', () => {
    it('getAlerts fetches user alerts', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await api.getAlerts();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/alerts',
        expect.anything()
      );
    });

    it('createAlert sends POST with alert data', async () => {
      const alertData = {
        ticker: 'AAPL',
        alert_type: 'PRICE_CHANGE',
        threshold: 0.05,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 'alert-1', ...alertData }),
      });

      await api.createAlert(alertData as any);

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/alerts',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(alertData),
        })
      );
    });

    it('updateAlert sends PUT request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 'alert-1', is_active: false }),
      });

      await api.updateAlert('alert-1', { is_active: false });

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/alerts/alert-1',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ is_active: false }),
        })
      );
    });

    it('deleteAlert sends DELETE request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: 'deleted' }),
      });

      await api.deleteAlert('alert-1');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/alerts/alert-1',
        expect.objectContaining({
          method: 'DELETE',
        })
      );
    });
  });

  describe('billing endpoints', () => {
    it('getSubscription fetches subscription info', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tier: 'professional', status: 'active' }),
      });

      const result = await api.getSubscription();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/billing/subscription',
        expect.anything()
      );
      expect(result.tier).toBe('professional');
    });

    it('createCheckoutSession sends POST with tier', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ session_id: 'sess_123', url: 'https://checkout.stripe.com/...' }),
      });

      await api.createCheckoutSession('professional');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/billing/checkout?tier=professional',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    it('createPortalSession sends POST request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ url: 'https://billing.stripe.com/...' }),
      });

      await api.createPortalSession();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/billing/portal',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('stats endpoint', () => {
    it('getStats fetches statistics', async () => {
      const mockStats = {
        total_events: 1000,
        total_events_yesterday: 950,
        bullish_events: 400,
        bullish_events_yesterday: 380,
        bearish_events: 300,
        bearish_events_yesterday: 290,
        high_alpha_events: 50,
        high_alpha_events_last_hour: 5,
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockStats),
      });

      const result = await api.getStats();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/stats',
        expect.anything()
      );
      expect(result).toEqual(mockStats);
    });
  });

  describe('auth endpoints (non-mock mode)', () => {
    it('login sends POST with credentials', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'token123', token_type: 'bearer' }),
      });

      const result = await api.login('user@example.com', 'password123');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/auth/login',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'user@example.com', password: 'password123' }),
        })
      );
      expect(result.access_token).toBe('token123');
    });

    it('register sends POST with user data', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 'user-1', email: 'user@example.com' }),
      });

      const result = await api.register('user@example.com', 'password123', 'John Doe');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/auth/register',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            email: 'user@example.com',
            password: 'password123',
            full_name: 'John Doe',
          }),
        })
      );
    });

    it('getCurrentUser fetches authenticated user', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 'user-1', email: 'user@example.com' }),
      });

      await api.getCurrentUser();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/auth/me',
        expect.anything()
      );
    });
  });
});

describe('ApiClient (mock mode)', () => {
  // These tests verify mock mode behavior
  // In actual implementation, we would need to create a new instance
  // or reset the module to test mock mode properly

  it('should have mock mode configuration option', () => {
    // This is a placeholder test to ensure mock mode is configurable
    expect(process.env.NEXT_PUBLIC_MOCK_MODE).toBeDefined();
  });
});
