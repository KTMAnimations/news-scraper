# Alert Configuration Guide

This guide provides detailed instructions for configuring alerts in Micro-Alpha. Alerts notify you when market events match your specified criteria, helping you stay ahead of market-moving news.

---

## Table of Contents

1. [Overview](#overview)
2. [Creating Your First Alert](#creating-your-first-alert)
3. [Alert Conditions](#alert-conditions)
4. [Notification Channels](#notification-channels)
5. [Managing Alerts](#managing-alerts)
6. [Alert Examples](#alert-examples)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

### What Are Alerts?

Alerts are custom rules that monitor incoming market events and notify you when specific conditions are met. When an event matches your alert criteria, you receive a notification via your chosen delivery method (push notification, email, or both).

### How Alerts Work

1. You define conditions (ticker, event type, alpha score, etc.)
2. The system continuously monitors incoming events
3. When an event matches ALL of your conditions, the alert triggers
4. You receive a notification with event details
5. The alert continues monitoring for future matches

### Alert Limits by Plan

| Plan | Active Alerts | Delivery Methods |
|------|---------------|------------------|
| Starter | 3 | Push only |
| Professional | 25 | Push + Email |
| Enterprise | Unlimited | Push + Email + Webhook |

---

## Creating Your First Alert

### Step 1: Navigate to Alerts

1. Click **Alerts** in the left sidebar
2. Click the **Create Alert** button in the top right

### Step 2: Name Your Alert

Give your alert a descriptive name that helps you identify it later.

**Good examples:**
- "AAPL Insider Buys"
- "High Alpha FDA Events"
- "Watchlist Earnings"

### Step 3: Configure Conditions

Set one or more conditions that events must match. See [Alert Conditions](#alert-conditions) for details.

### Step 4: Choose Delivery Method

Select how you want to be notified:
- **Push**: Mobile/browser push notifications
- **Email**: Email to your registered address
- **Both**: Receive both push and email

### Step 5: Save and Activate

Click **Create Alert** to save. The alert is automatically activated and begins monitoring immediately.

---

## Alert Conditions

Alerts trigger when an incoming event matches ALL specified conditions. Leave a condition empty to match all values.

### Ticker Filter

Restrict the alert to events for a specific stock symbol.

| Setting | Behavior |
|---------|----------|
| Empty | Matches events for ALL tickers |
| `AAPL` | Only matches events for Apple Inc. |
| Case | Automatically converted to uppercase |

**Use cases:**
- Monitor a specific stock in your portfolio
- Track a potential investment opportunity
- Follow a competitor

### Direction Filter

Filter by the signal direction of events.

| Direction | Description |
|-----------|-------------|
| Any | Matches all directions |
| BULLISH | Only positive/bullish signals |
| BEARISH | Only negative/bearish signals |

**Use cases:**
- Alert only on bullish news for stocks you own
- Alert on bearish news for potential short opportunities
- Track any direction for comprehensive monitoring

### Minimum Alpha Score

Only trigger for events above a certain conviction level.

| Range | Meaning |
|-------|---------|
| 0-49 | Lower conviction signals |
| 50-69 | Medium conviction signals |
| 70-79 | High conviction signals |
| 80-100 | Critical/urgent signals |

**Recommendations:**
- Set to 70+ for actionable trading signals
- Set to 50+ for broader monitoring
- Set to 80+ for critical-only alerts

### Urgency Levels

Filter by the urgency classification of events.

| Level | Description | Typical Events |
|-------|-------------|----------------|
| CRITICAL | Requires immediate attention | FDA decisions, bankruptcy, major acquisitions |
| HIGH | High priority, act within hours | Insider trades, activist stakes, earnings surprises |
| MEDIUM | Worth monitoring | Press releases, management changes |
| LOW | Informational | Social mentions, analyst opinions |

**Selection behavior:**
- Select multiple levels by clicking each button
- Leave empty to match all urgency levels
- Selected levels are highlighted

### Event Types

Filter by specific categories of events.

**Available Event Types:**

| Category | Event Types |
|----------|-------------|
| SEC Filings | `SEC_FILING`, `INSIDER_BUY`, `INSIDER_SELL`, `ACTIVIST_STAKE` |
| Earnings | `EARNINGS_BEAT`, `EARNINGS_MISS` |
| FDA | `FDA_APPROVAL`, `FDA_REJECTION` |
| Corporate | `ACQUISITION`, `BANKRUPTCY`, `OFFERING`, `MANAGEMENT_CHANGE` |
| Regulatory | `REGULATORY_ACTION` |
| News | `NEWS`, `SOCIAL_MENTION` |

**Selection behavior:**
- Select multiple event types by clicking each button
- Leave empty to match all event types
- Selected types are highlighted in accent color

---

## Notification Channels

### Push Notifications

Push notifications deliver instant alerts to your device.

**Setup Requirements:**
1. Allow notifications when prompted by your browser
2. For mobile, install the Micro-Alpha app (coming soon)

**Characteristics:**
- Near-instant delivery (under 5 seconds)
- Works even when app is in background
- Includes event headline and key details
- Click to view full event

### Email Notifications

Email notifications provide detailed event information.

**Setup:**
- Uses your registered email address
- No additional configuration required

**Characteristics:**
- Delivery within 1-2 minutes
- Includes full event details
- Contains direct links to ticker page
- Can be filtered to specific folders

### Combined Delivery (Both)

Select "Both" to receive notifications through all channels.

**Best for:**
- Critical alerts you cannot miss
- Important tickers in your portfolio
- High-stakes trading opportunities

---

## Managing Alerts

### Viewing Your Alerts

The Alerts page displays all your configured alerts with:
- Alert name and conditions summary
- Active/paused status
- Last triggered time
- Edit and delete actions

### Pausing Alerts

Temporarily disable an alert without deleting it:

1. Find the alert in your list
2. Click the power icon on the left
3. The alert turns gray and stops monitoring
4. Click again to reactivate

**Use cases:**
- Pause during market holidays
- Temporarily mute noisy alerts
- Disable while traveling

### Editing Alerts

Modify an existing alert:

1. Click the edit (pencil) icon on the alert
2. Update any conditions
3. Click **Update Alert** to save

Changes take effect immediately for new events.

### Deleting Alerts

Permanently remove an alert:

1. Click the delete (trash) icon on the alert
2. The alert is immediately deleted

**Note:** Deleted alerts cannot be recovered.

### Alert Statistics

The page header shows key statistics:
- **Active Alerts**: Currently monitoring
- **Paused Alerts**: Disabled but saved
- **Triggered Today**: Alerts that matched events today

---

## Alert Examples

### Example 1: Insider Buying Alert

Monitor for insider purchases, which often precede positive price movements.

```
Name: Insider Buying Signals
Ticker: [empty - all tickers]
Direction: BULLISH
Min Alpha Score: 60
Urgency Levels: HIGH, CRITICAL
Event Types: INSIDER_BUY
Delivery: Push
```

### Example 2: Specific Stock Monitor

Track all significant events for a stock you own.

```
Name: NVDA All Events
Ticker: NVDA
Direction: Any
Min Alpha Score: 50
Urgency Levels: HIGH, CRITICAL
Event Types: [empty - all types]
Delivery: Both
```

### Example 3: FDA Event Tracker

Alert on any FDA-related news for biotech trading.

```
Name: FDA News Alert
Ticker: [empty - all tickers]
Direction: Any
Min Alpha Score: 70
Urgency Levels: CRITICAL
Event Types: FDA_APPROVAL, FDA_REJECTION
Delivery: Both
```

### Example 4: Bearish Signal Warning

Get warned about potential negative catalysts.

```
Name: Bearish High Alpha Signals
Ticker: [empty - all tickers]
Direction: BEARISH
Min Alpha Score: 75
Urgency Levels: HIGH, CRITICAL
Event Types: BANKRUPTCY, EARNINGS_MISS, FDA_REJECTION, REGULATORY_ACTION
Delivery: Email
```

### Example 5: SEC Filing Monitor

Track important SEC filings for activist activity.

```
Name: Activist Stakes
Ticker: [empty - all tickers]
Direction: Any
Min Alpha Score: 65
Urgency Levels: HIGH
Event Types: ACTIVIST_STAKE
Delivery: Push
```

### Example 6: Critical Events Only

Minimal alerts for only the most significant events.

```
Name: Critical Alpha Only
Ticker: [empty - all tickers]
Direction: Any
Min Alpha Score: 85
Urgency Levels: CRITICAL
Event Types: [empty - all types]
Delivery: Both
```

---

## Best Practices

### 1. Start Specific, Then Broaden

Begin with narrow conditions and expand if you're not getting enough alerts.

**Bad approach:**
- Alpha > 30, all types, all tickers = too many alerts

**Good approach:**
- Alpha > 70, specific types, specific ticker = actionable alerts

### 2. Use Urgency Levels Effectively

- For trading alerts: HIGH and CRITICAL only
- For research alerts: Include MEDIUM
- Never include LOW for real-time alerts (too noisy)

### 3. Match Delivery to Urgency

| Alert Importance | Recommended Delivery |
|------------------|---------------------|
| Critical portfolio risk | Both (Push + Email) |
| Trading opportunities | Push only |
| Research/monitoring | Email only |

### 4. Name Alerts Descriptively

Good names help you manage alerts:
- Include the ticker if specific: "TSLA Earnings"
- Include the purpose: "FDA Opportunities"
- Include the type: "Insider Buy Tracker"

### 5. Review and Prune Regularly

- Check alerts weekly for relevance
- Pause alerts for stocks you've sold
- Delete alerts that never trigger
- Adjust alpha thresholds based on volume

### 6. Avoid Alert Fatigue

- Limit to 5-10 active alerts
- Prioritize quality over quantity
- Use email for lower-priority alerts
- Review triggered alerts to refine conditions

---

## Troubleshooting

### Alert Not Triggering

**Possible causes:**

1. **Conditions too narrow**
   - Lower the alpha score threshold
   - Add more event types
   - Remove ticker filter to test

2. **Alert is paused**
   - Check the power icon is green
   - Click to reactivate if gray

3. **No matching events**
   - Some tickers have few events
   - Check the ticker's event history

### Too Many Alerts

**Solutions:**

1. Increase minimum alpha score
2. Limit to HIGH/CRITICAL urgency
3. Add a specific ticker filter
4. Reduce event types

### Push Notifications Not Arriving

**Troubleshooting steps:**

1. Check browser notification permissions
2. Ensure notifications aren't blocked
3. Verify "Real-time Alerts" is enabled in Settings
4. Clear browser cache and re-enable

### Email Notifications Delayed

**Possible causes:**

1. Email provider rate limiting
2. Check spam/junk folder
3. Verify email address in Settings

### Alert Triggered But Event Not Found

**Explanation:**

Events may be deduplicated or updated. The alert triggers on first receipt, but the event display may show the merged/updated version.

---

## API Access

For programmatic alert management, use the REST API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/alerts` | GET | List all alerts |
| `/api/v1/alerts` | POST | Create new alert |
| `/api/v1/alerts/{id}` | PUT | Update alert |
| `/api/v1/alerts/{id}` | DELETE | Delete alert |

See the API documentation at `/api/docs` for full details.

---

## Alert Payload Format

When an alert triggers, you receive a notification with:

```json
{
  "alert_name": "High Alpha FDA Events",
  "event": {
    "ticker": "MRNA",
    "headline": "Moderna Receives FDA Approval for New Vaccine",
    "event_type": "FDA_APPROVAL",
    "direction": "BULLISH",
    "alpha_score": 87,
    "sentiment_label": "positive",
    "event_time": "2026-01-23T14:30:00Z"
  }
}
```

---

*Last Updated: January 2026*
