# Micro-Alpha User Guide

Welcome to Micro-Alpha, a real-time financial news aggregation and analysis platform designed for traders focused on micro-cap and small-cap stocks. This guide will help you get started and make the most of the platform's features.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Event Feed](#event-feed)
4. [High Alpha Signals](#high-alpha-signals)
5. [Ticker Detail Pages](#ticker-detail-pages)
6. [Watchlist Management](#watchlist-management)
7. [Alert Configuration](#alert-configuration)
8. [Search](#search)
9. [Settings & Preferences](#settings--preferences)
10. [Theme Settings](#theme-settings)

---

## Getting Started

### Creating Your Account

1. Navigate to the Micro-Alpha website
2. Click **Register** to create a new account
3. Enter your email address and create a secure password
4. Verify your email address by clicking the link sent to your inbox
5. Log in with your credentials

### First Login

After logging in for the first time, you will be directed to the main dashboard. Take a moment to:

- Explore the navigation sidebar on the left
- Review the live event feed
- Add your first tickers to your watchlist
- Configure your alert preferences

### Understanding the Interface

The Micro-Alpha interface consists of:

- **Header**: Contains the logo, search bar, theme toggle, and user menu
- **Sidebar**: Main navigation with quick access to all features and live activity stats
- **Main Content Area**: Displays the current page content (dashboard, feed, etc.)

---

## Dashboard Overview

The Dashboard is your command center for monitoring market events in real-time.

### Stats Cards

At the top of the dashboard, you'll find four key metrics:

| Metric | Description |
|--------|-------------|
| **Total Events** | The total number of events captured today, with percentage change vs. yesterday |
| **Bullish Signals** | Events with positive sentiment or direction, indicating potential upward movement |
| **Bearish Signals** | Events with negative sentiment or direction, indicating potential downward movement |
| **High Alpha** | Events with alpha scores above 70, representing high-conviction trading opportunities |

### Live Feed Status

The top-right corner displays your connection status:
- **Green dot with "Live Feed Active"**: You are receiving real-time updates
- **Red dot with "Disconnected"**: The connection was lost; events will refresh on page reload

### Latest Events Panel

The main panel displays the most recent events sorted by time. Each event card shows:

- **Ticker symbol**: Click to view the ticker detail page
- **Headline**: Summary of the event
- **Event type**: Category of the event (e.g., SEC Filing, Insider Trade)
- **Sentiment**: Positive, negative, or neutral indicator
- **Direction**: BULLISH, BEARISH, or NEUTRAL
- **Alpha score**: Signal strength indicator (0-100)
- **Time**: When the event was published

### High Alpha Sidebar

The right sidebar highlights events with alpha scores greater than 70. These represent:
- High-conviction trading signals
- Material events likely to move stock prices
- Opportunities requiring immediate attention

---

## Event Feed

The Event Feed page (`/dashboard/feed`) provides a comprehensive view of all market events with powerful filtering and sorting capabilities.

### Filtering Events

Click the **Filters** button to reveal the filter panel. Available filters include:

| Filter | Description |
|--------|-------------|
| **Ticker** | Filter by specific stock symbol (e.g., AAPL, TSLA) |
| **Event Type** | Filter by category (Insider Buy, FDA Approval, Earnings, etc.) |
| **Direction** | Filter by BULLISH, BEARISH, or NEUTRAL signals |
| **Sentiment** | Filter by positive, negative, or neutral sentiment |
| **Min Alpha Score** | Only show events above a certain alpha threshold (0-100) |
| **Source** | Filter by news source (SEC EDGAR, PR Newswire, etc.) |
| **Date Range** | Filter events within a specific time period |

### Sorting Events

Use the sort controls to order events by:
- **Time**: Most recent or oldest first
- **Alpha Score**: Highest or lowest conviction first
- **Sentiment Score**: Most positive or most negative first

### Pagination

Navigate through results using the pagination controls at the bottom. The system shows 20 events per page by default.

### Event Types

Micro-Alpha captures and categorizes the following event types:

| Event Type | Description |
|------------|-------------|
| `INSIDER_BUY` | Company insider purchasing shares |
| `INSIDER_SELL` | Company insider selling shares |
| `EARNINGS_BEAT` | Company exceeds earnings expectations |
| `EARNINGS_MISS` | Company misses earnings expectations |
| `FDA_APPROVAL` | Drug or device receives FDA approval |
| `FDA_REJECTION` | Drug or device FDA application rejected |
| `ACQUISITION` | Company being acquired or acquiring another |
| `BANKRUPTCY` | Bankruptcy filing or proceedings |
| `ACTIVIST_STAKE` | Activist investor takes significant position |
| `OFFERING` | Stock offering or equity raise |
| `MANAGEMENT_CHANGE` | CEO, CFO, or board changes |
| `REGULATORY_ACTION` | Government regulatory action |
| `SEC_FILING` | New SEC filing (8-K, Form 4, 13D, etc.) |
| `NEWS` | General news coverage |
| `SOCIAL_MENTION` | Social media buzz or trending discussion |

---

## High Alpha Signals

The High Alpha page (`/dashboard/high-alpha`) is dedicated to the most actionable trading signals.

### What is Alpha Score?

The alpha score is a composite metric (0-100) that combines multiple factors to identify high-conviction trading opportunities:

| Factor | Weight | Description |
|--------|--------|-------------|
| Event Type | 35% | Material events (insider buys, FDA approvals) score higher |
| Sentiment | 25% | Strong positive or negative sentiment increases score |
| Source Reliability | 15% | SEC filings and official sources score higher than social media |
| Recency | 15% | More recent events score higher (exponential decay) |
| Liquidity | 10% | Micro-cap and small-cap stocks score higher (more alpha potential) |

### Interpreting Signals

- **Alpha 80-100**: Critical signal, requires immediate attention
- **Alpha 70-79**: High-priority signal, strong conviction
- **Alpha 50-69**: Medium signal, worth monitoring
- **Alpha below 50**: Lower conviction, informational

### Direction Indicators

Each high-alpha signal includes a direction:
- **BULLISH** (green): Positive catalyst, potential upward price movement
- **BEARISH** (red): Negative catalyst, potential downward price movement
- **NEUTRAL**: Information only, direction unclear

---

## Ticker Detail Pages

Click on any ticker symbol to access its dedicated detail page (`/dashboard/ticker/[SYMBOL]`).

### Page Overview

The ticker detail page provides comprehensive analysis including:

1. **Header**: Ticker symbol, watchlist toggle, and time range selector
2. **Stats Row**: Total events, bullish/bearish counts, high alpha signals, average sentiment
3. **Price Chart**: Interactive TradingView chart with technical analysis tools
4. **Event Activity Chart**: Visual representation of event volume over the last 24 hours
5. **Sentiment Analysis**: Overall sentiment breakdown and trend
6. **Recent Events**: Complete event history for the ticker

### Price Chart Features

The TradingView chart integration provides:
- Multiple timeframes (1D, 1W, 1M, etc.)
- Technical indicators
- Drawing tools
- Full-screen mode
- Direct link to TradingView for advanced analysis

### Sentiment Analysis Panel

The sentiment panel shows:
- **Overall Sentiment**: Sliding scale from Bearish to Bullish
- **Event Type Distribution**: Most common event types for this ticker
- **Sentiment Trend**: Whether sentiment is improving, declining, or stable

### Time Range Selection

Filter events by time period:
- Last 6 hours
- Last 24 hours (default)
- Last 48 hours
- Last 7 days

### Watchlist Toggle

Click the star icon to add/remove the ticker from your watchlist directly from the detail page.

---

## Watchlist Management

The Watchlist page (`/dashboard/watchlist`) helps you track your favorite tickers and monitor their events.

### Adding Tickers

1. Click the **Add Ticker** button
2. Enter the ticker symbol (e.g., AAPL)
3. Optionally add notes about why you're watching this stock
4. Click **Add to Watchlist**

### Viewing Watchlist

Your watchlist displays:
- All watched tickers in a scrollable list
- Notes you've added for each ticker
- When each ticker was added
- Quick access to edit or remove

### Ticker Events Panel

When you select a ticker from your watchlist:
1. The right panel shows all recent events for that ticker
2. Events display with full details including sentiment and alpha score
3. High alpha signals are highlighted

### Watchlist Stats

The stats cards show:
- **Watching**: Total number of tickers in your watchlist
- **Selected Ticker Events**: Event count for the currently selected ticker
- **High Alpha**: High alpha signals detected for selected ticker

### Managing Entries

For each watchlist entry, you can:
- **Edit Notes**: Click the edit icon to update your notes
- **Remove**: Click the trash icon to remove from watchlist
- **View Details**: Click the ticker to navigate to its detail page

---

## Alert Configuration

Alerts notify you when specific market conditions are met. See the separate [Alert Configuration Guide](./ALERT_CONFIGURATION.md) for detailed instructions.

### Quick Start

1. Go to **Alerts** in the sidebar
2. Click **Create Alert**
3. Configure your alert conditions
4. Choose delivery method (push, email, or both)
5. Save and activate

### Alert Stats

The Alerts page displays:
- **Active Alerts**: Currently monitoring alerts
- **Paused Alerts**: Disabled alerts (can be reactivated)
- **Triggered Today**: Alerts that fired today

---

## Search

The Search page (`/dashboard/search`) provides full-text search across all events.

### Search Tips

- Search by ticker: `AAPL` or `$AAPL`
- Search by company name: `Apple Inc`
- Search by keyword: `FDA approval`
- Search by event type: `insider buy`
- Combine terms: `AAPL FDA`

### Search Results

Results are sorted by relevance and show:
- Event headline and summary
- Ticker symbol(s) mentioned
- Event type and sentiment
- Publication date

---

## Settings & Preferences

Access Settings from the sidebar to manage your account.

### Profile Tab

Manage your personal information:
- Update your display name
- View your email address
- Add company information (optional)
- See your current subscription tier

### Notifications Tab

Configure how you receive notifications:

**Email Notifications:**
- Alert Notifications: Get emails when alerts trigger
- Daily Digest: Summary of high-alpha events each day
- Weekly Report: Comprehensive weekly market analysis
- Product Updates: New features and improvements

**Push Notifications:**
- Real-time Alerts: Instant notifications for triggered alerts
- High Alpha Signals: Notifications for signals with alpha > 80

### Billing Tab

Manage your subscription:
- View current plan and features
- Upgrade to Professional or Enterprise
- Access billing portal for payment management
- View available plans and pricing

**Subscription Tiers:**

| Tier | Price | Key Features |
|------|-------|--------------|
| Starter | Free | Basic event feed, limited watchlist |
| Professional | $49/mo | Unlimited watchlist, real-time alerts, API access |
| Enterprise | Custom | Dedicated support, custom integrations, SLA |

### Security Tab

Protect your account:
- Change password
- Enable two-factor authentication (2FA)
- View active sessions
- Sign out of other devices
- Delete account (danger zone)

---

## Theme Settings

Micro-Alpha supports both light and dark themes for comfortable viewing.

### Switching Themes

1. Click the sun/moon icon in the header
2. The theme toggles between light and dark mode
3. Your preference is saved automatically

### Theme Behavior

- **Dark Mode**: Optimized for low-light environments and extended viewing
- **Light Mode**: High contrast for bright environments
- **System Default**: Automatically matches your operating system preference

### Charts and Theme

The TradingView charts automatically adapt to your selected theme for a consistent experience.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus search bar |
| `r` | Refresh current page |
| `d` | Go to Dashboard |
| `f` | Go to Event Feed |
| `w` | Go to Watchlist |
| `a` | Go to Alerts |
| `s` | Go to Settings |

---

## Getting Help

If you need assistance:

1. **FAQ**: Check the [Frequently Asked Questions](./FAQ.md)
2. **Email Support**: support@micro-alpha.com
3. **Documentation**: Full API documentation at `/api/docs`

---

## Best Practices

### For Day Traders

1. Focus on the High Alpha page for immediate opportunities
2. Set alerts for your key tickers with high alpha thresholds
3. Use the 6-hour time range for intraday analysis
4. Monitor the live feed during market hours

### For Swing Traders

1. Review the Daily Digest emails
2. Focus on events with alpha 60-80 for developing opportunities
3. Use the 7-day time range on ticker detail pages
4. Add notes to watchlist entries with your thesis

### For Quant Traders

1. Use the REST API for automated data access
2. Export historical data for backtesting
3. Subscribe to WebSocket for real-time event streaming
4. Leverage the alpha score factors in your models

---

*Last Updated: January 2026*
