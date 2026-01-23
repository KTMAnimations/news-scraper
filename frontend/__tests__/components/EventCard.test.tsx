import { render, screen, fireEvent } from '../test-utils';
import { EventCard } from '@/components/events/EventCard';
import type { Event } from '@/types/events';

// Mock the SentimentBadge component
jest.mock('@/components/events/SentimentBadge', () => ({
  SentimentBadge: ({ sentiment, confidence }: { sentiment: string; confidence?: number }) => (
    <span data-testid="sentiment-badge">
      {sentiment} {confidence && `(${(confidence * 100).toFixed(0)}%)`}
    </span>
  ),
}));

// Mock the WatchlistButton component
jest.mock('@/components/watchlist/WatchlistButton', () => ({
  WatchlistButton: ({ ticker }: { ticker: string }) => (
    <button data-testid="watchlist-button" aria-label={`Add ${ticker} to watchlist`}>
      Watchlist
    </button>
  ),
}));

const mockEvent: Event = {
  id: 'test-event-1',
  ticker: 'AAPL',
  event_time: '2026-01-23T10:30:00Z',
  ingest_time: '2026-01-23T10:31:00Z',
  event_type: 'INSIDER_BUY',
  headline: 'Apple CEO buys 100,000 shares worth $15M',
  summary: 'Tim Cook purchased shares signaling strong confidence in the company.',
  source_url: 'https://example.com/article',
  source_name: 'SEC EDGAR',
  sentiment_score: 0.85,
  sentiment_label: 'positive',
  sentiment_confidence: 0.92,
  alpha_score: 0.75,
  direction: 'BULLISH',
  urgency: 'HIGH',
  extracted_tickers: ['AAPL', 'MSFT'],
  extracted_people: ['Tim Cook'],
};

describe('EventCard', () => {
  describe('basic rendering', () => {
    it('renders the event headline', () => {
      render(<EventCard event={mockEvent} />);
      expect(screen.getByText('Apple CEO buys 100,000 shares worth $15M')).toBeInTheDocument();
    });

    it('renders the ticker as a link', () => {
      render(<EventCard event={mockEvent} />);
      const tickerLink = screen.getByText('AAPL');
      expect(tickerLink).toBeInTheDocument();
      expect(tickerLink.closest('a')).toHaveAttribute('href', '/dashboard/ticker/AAPL');
    });

    it('renders the event type badge', () => {
      render(<EventCard event={mockEvent} />);
      expect(screen.getByText('INSIDER BUY')).toBeInTheDocument();
    });

    it('renders the source name', () => {
      render(<EventCard event={mockEvent} />);
      expect(screen.getByText('SEC EDGAR')).toBeInTheDocument();
    });

    it('renders the direction indicator', () => {
      render(<EventCard event={mockEvent} />);
      expect(screen.getByText('BULLISH')).toBeInTheDocument();
    });
  });

  describe('alpha score display', () => {
    it('displays the alpha score', () => {
      render(<EventCard event={mockEvent} />);
      expect(screen.getByText('75')).toBeInTheDocument();
      expect(screen.getByText('Alpha')).toBeInTheDocument();
    });

    it('shows High Alpha badge for high alpha events', () => {
      render(<EventCard event={mockEvent} />);
      expect(screen.getByText('High Alpha')).toBeInTheDocument();
    });

    it('does not show High Alpha badge for low alpha events', () => {
      const lowAlphaEvent = { ...mockEvent, alpha_score: 0.3 };
      render(<EventCard event={lowAlphaEvent} />);
      expect(screen.queryByText('High Alpha')).not.toBeInTheDocument();
    });

    it('handles undefined alpha score', () => {
      const noAlphaEvent = { ...mockEvent, alpha_score: undefined };
      render(<EventCard event={noAlphaEvent} />);
      expect(screen.queryByText('Alpha')).not.toBeInTheDocument();
    });
  });

  describe('direction styling', () => {
    it('applies bullish styling for BULLISH direction', () => {
      render(<EventCard event={mockEvent} />);
      const directionBadge = screen.getByText('BULLISH').closest('div');
      expect(directionBadge).toHaveClass('text-positive');
    });

    it('applies bearish styling for BEARISH direction', () => {
      const bearishEvent = { ...mockEvent, direction: 'BEARISH' as const };
      render(<EventCard event={bearishEvent} />);
      const directionBadge = screen.getByText('BEARISH').closest('div');
      expect(directionBadge).toHaveClass('text-negative');
    });

    it('applies neutral styling for NEUTRAL direction', () => {
      const neutralEvent = { ...mockEvent, direction: 'NEUTRAL' as const };
      render(<EventCard event={neutralEvent} />);
      const directionBadge = screen.getByText('NEUTRAL').closest('div');
      expect(directionBadge).toHaveClass('text-text-tertiary');
    });
  });

  describe('expansion behavior', () => {
    it('expands to show details when clicked', () => {
      render(<EventCard event={mockEvent} />);

      // Summary should not be visible initially
      expect(screen.queryByText('Tim Cook purchased shares signaling strong confidence in the company.')).not.toBeInTheDocument();

      // Click to expand
      const card = screen.getByText('Apple CEO buys 100,000 shares worth $15M').closest('div');
      fireEvent.click(card!.parentElement!.parentElement!);

      // Summary should now be visible
      expect(screen.getByText('Tim Cook purchased shares signaling strong confidence in the company.')).toBeInTheDocument();
    });

    it('shows sentiment badge when expanded', () => {
      render(<EventCard event={mockEvent} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);

      // Sentiment badge should be visible
      expect(screen.getByTestId('sentiment-badge')).toBeInTheDocument();
    });

    it('shows related tickers when expanded', () => {
      render(<EventCard event={mockEvent} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);

      // Related tickers should be visible
      expect(screen.getByText('Related Tickers')).toBeInTheDocument();
      expect(screen.getAllByText('MSFT').length).toBeGreaterThan(0);
    });

    it('shows extracted people when expanded', () => {
      render(<EventCard event={mockEvent} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);

      // People should be visible
      expect(screen.getByText('People')).toBeInTheDocument();
      expect(screen.getByText('Tim Cook')).toBeInTheDocument();
    });

    it('shows source link when expanded', () => {
      render(<EventCard event={mockEvent} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);

      // Source link should be visible
      const sourceLink = screen.getByText('View source');
      expect(sourceLink).toBeInTheDocument();
      expect(sourceLink.closest('a')).toHaveAttribute('href', 'https://example.com/article');
    });

    it('collapses when clicked again', () => {
      render(<EventCard event={mockEvent} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);
      expect(screen.getByText('Tim Cook purchased shares signaling strong confidence in the company.')).toBeInTheDocument();

      // Click to collapse
      fireEvent.click(headline.closest('[class*="p-5"]')!);
      expect(screen.queryByText('Tim Cook purchased shares signaling strong confidence in the company.')).not.toBeInTheDocument();
    });
  });

  describe('compact mode', () => {
    it('applies smaller text in compact mode', () => {
      render(<EventCard event={mockEvent} compact />);
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      expect(headline).toHaveClass('text-sm');
    });

    it('applies normal text size by default', () => {
      render(<EventCard event={mockEvent} />);
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      expect(headline).toHaveClass('text-base');
    });
  });

  describe('missing data handling', () => {
    it('handles missing source_name', () => {
      const eventWithoutSource = { ...mockEvent, source_name: undefined };
      render(<EventCard event={eventWithoutSource} />);
      expect(screen.queryByText('SEC EDGAR')).not.toBeInTheDocument();
    });

    it('handles missing summary', () => {
      const eventWithoutSummary = { ...mockEvent, summary: undefined };
      render(<EventCard event={eventWithoutSummary} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);

      // Should still render without summary
      expect(screen.getByText('Event Time')).toBeInTheDocument();
    });

    it('handles missing extracted_tickers', () => {
      const eventWithoutTickers = { ...mockEvent, extracted_tickers: undefined };
      render(<EventCard event={eventWithoutTickers} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);

      expect(screen.queryByText('Related Tickers')).not.toBeInTheDocument();
    });

    it('handles empty extracted_tickers array', () => {
      const eventWithEmptyTickers = { ...mockEvent, extracted_tickers: [] };
      render(<EventCard event={eventWithEmptyTickers} />);

      // Click to expand
      const headline = screen.getByText('Apple CEO buys 100,000 shares worth $15M');
      fireEvent.click(headline.closest('[class*="p-5"]')!);

      expect(screen.queryByText('Related Tickers')).not.toBeInTheDocument();
    });
  });

  describe('link click propagation', () => {
    it('prevents card expansion when clicking ticker link', () => {
      render(<EventCard event={mockEvent} />);

      // Click the ticker link
      const tickerLink = screen.getByText('AAPL');
      fireEvent.click(tickerLink);

      // Card should not be expanded
      expect(screen.queryByText('Tim Cook purchased shares signaling strong confidence in the company.')).not.toBeInTheDocument();
    });
  });
});
