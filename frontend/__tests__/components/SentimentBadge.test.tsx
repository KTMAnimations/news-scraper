import { render, screen } from '@testing-library/react';
import { SentimentBadge } from '@/components/events/SentimentBadge';

describe('SentimentBadge', () => {
  describe('rendering', () => {
    it('renders positive sentiment correctly', () => {
      render(<SentimentBadge sentiment="positive" />);
      expect(screen.getByText('Positive')).toBeInTheDocument();
    });

    it('renders negative sentiment correctly', () => {
      render(<SentimentBadge sentiment="negative" />);
      expect(screen.getByText('Negative')).toBeInTheDocument();
    });

    it('renders neutral sentiment correctly', () => {
      render(<SentimentBadge sentiment="neutral" />);
      expect(screen.getByText('Neutral')).toBeInTheDocument();
    });
  });

  describe('confidence display', () => {
    it('shows confidence percentage when provided', () => {
      render(<SentimentBadge sentiment="positive" confidence={0.85} />);
      expect(screen.getByText('Positive')).toBeInTheDocument();
      expect(screen.getByText('(85%)')).toBeInTheDocument();
    });

    it('hides confidence when showConfidence is false', () => {
      render(<SentimentBadge sentiment="positive" confidence={0.85} showConfidence={false} />);
      expect(screen.getByText('Positive')).toBeInTheDocument();
      expect(screen.queryByText('(85%)')).not.toBeInTheDocument();
    });

    it('does not show confidence when not provided', () => {
      render(<SentimentBadge sentiment="positive" />);
      expect(screen.queryByText(/\(\d+%\)/)).not.toBeInTheDocument();
    });

    it('rounds confidence to whole number', () => {
      render(<SentimentBadge sentiment="negative" confidence={0.756} />);
      expect(screen.getByText('(76%)')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies positive badge classes for positive sentiment', () => {
      const { container } = render(<SentimentBadge sentiment="positive" />);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('badge-positive');
    });

    it('applies negative badge classes for negative sentiment', () => {
      const { container } = render(<SentimentBadge sentiment="negative" />);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('badge-negative');
    });

    it('applies neutral badge classes for neutral sentiment', () => {
      const { container } = render(<SentimentBadge sentiment="neutral" />);
      const badge = container.querySelector('span');
      expect(badge).toHaveClass('badge-neutral');
    });

    it('includes sentiment indicator dot', () => {
      const { container } = render(<SentimentBadge sentiment="positive" />);
      const dot = container.querySelector('.bg-positive');
      expect(dot).toBeInTheDocument();
    });
  });
});
