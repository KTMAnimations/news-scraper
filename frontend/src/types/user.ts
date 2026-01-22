export type SubscriptionTier = 'starter' | 'professional' | 'team' | 'enterprise';
export type SubscriptionStatus = 'active' | 'canceled' | 'past_due' | 'trialing';

export interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_verified: boolean;

  // Subscription
  subscription_tier: SubscriptionTier;
  subscription_status: SubscriptionStatus;

  // Metadata
  created_at: string;
  last_login?: string;
}

export interface WatchlistItem {
  id: string;
  ticker: string;
  added_at: string;
  notes?: string;
}

export interface Alert {
  id: string;
  name: string;
  ticker?: string;
  event_types?: string[];
  min_alpha_score?: number;
  urgency_levels?: string[];
  direction?: string;
  delivery_method: 'push' | 'email' | 'both';
  is_active: boolean;
  created_at: string;
  last_triggered_at?: string;
}

export interface AlertCreate {
  name: string;
  ticker?: string;
  event_types?: string[];
  min_alpha_score?: number;
  urgency_levels?: string[];
  direction?: string;
  delivery_method?: 'push' | 'email' | 'both';
}

export const TIER_FEATURES: Record<
  SubscriptionTier,
  {
    name: string;
    price: number;
    seats: number;
    features: string[];
  }
> = {
  starter: {
    name: 'Starter',
    price: 299,
    seats: 1,
    features: [
      'Core event feed',
      '5 watchlist tickers',
      'Email alerts',
      '24h data retention',
    ],
  },
  professional: {
    name: 'Professional',
    price: 799,
    seats: 3,
    features: [
      'Full event feed',
      'Unlimited watchlist',
      'Real-time push alerts',
      'API access (100 req/min)',
      '90 day data retention',
    ],
  },
  team: {
    name: 'Team',
    price: 1999,
    seats: 10,
    features: [
      'Everything in Professional',
      'API access (1000 req/min)',
      'Custom integrations',
      'Priority support',
      'Full data history',
    ],
  },
  enterprise: {
    name: 'Enterprise',
    price: 0, // Contact for pricing
    seats: -1, // Custom
    features: [
      'Everything in Team',
      'Dedicated support',
      'SLA guarantee',
      'White-label options',
      'Custom data sources',
    ],
  },
};
