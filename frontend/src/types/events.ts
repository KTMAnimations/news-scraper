export type SentimentLabel = 'positive' | 'negative' | 'neutral';
export type Direction = 'BULLISH' | 'BEARISH' | 'NEUTRAL';
export type Urgency = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface Event {
  id: string;
  ticker: string;
  event_time: string;
  ingest_time: string;

  // Classification
  event_type: string;
  event_category?: string;

  // Content
  headline: string;
  summary?: string;
  content?: string;
  source_url?: string;
  source_name?: string;

  // Sentiment & Scoring
  sentiment_score?: number;
  sentiment_label?: SentimentLabel;
  sentiment_confidence?: number;
  alpha_score?: number;
  direction?: Direction;
  urgency?: Urgency;

  // Entities
  extracted_tickers?: string[];
  extracted_companies?: string[];
  extracted_people?: string[];
  extracted_amounts?: Record<string, number>;

  // Metadata
  metadata?: Record<string, unknown>;
}

export interface EventFilters {
  ticker?: string;
  event_type?: string;
  sentiment_label?: SentimentLabel;
  direction?: Direction;
  min_alpha_score?: number;
  source_name?: string;
  start_date?: string;
  end_date?: string;
}

export interface EventsResponse {
  events: Event[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SentimentAggregate {
  ticker: string;
  hour: string;
  avg_sentiment: number;
  event_count: number;
  max_alpha: number;
  min_alpha: number;
}

export const EVENT_TYPES = [
  'INSIDER_BUY',
  'INSIDER_SELL',
  'EARNINGS_BEAT',
  'EARNINGS_MISS',
  'FDA_APPROVAL',
  'FDA_REJECTION',
  'ACQUISITION',
  'BANKRUPTCY',
  'ACTIVIST_STAKE',
  'OFFERING',
  'MANAGEMENT_CHANGE',
  'REGULATORY_ACTION',
  'SEC_FILING',
  'NEWS',
  'SOCIAL_MENTION',
] as const;

export type EventType = (typeof EVENT_TYPES)[number];
