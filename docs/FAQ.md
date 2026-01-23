# Frequently Asked Questions (FAQ)

This document answers common questions about Micro-Alpha. For more detailed information, see the [User Guide](./USER_GUIDE.md) and [Alert Configuration Guide](./ALERT_CONFIGURATION.md).

---

## Table of Contents

1. [Account Questions](#account-questions)
2. [Feature Questions](#feature-questions)
3. [Technical Questions](#technical-questions)
4. [Troubleshooting](#troubleshooting)
5. [Billing & Subscription](#billing--subscription)
6. [Data & Privacy](#data--privacy)

---

## Account Questions

### How do I create an account?

1. Visit the Micro-Alpha website
2. Click **Register** in the top navigation
3. Enter your email address and choose a secure password
4. Click the verification link sent to your email
5. Log in with your new credentials

### Can I change my email address?

Currently, email addresses cannot be changed after registration. If you need to use a different email, please contact support at support@micro-alpha.com.

### How do I reset my password?

1. Go to the login page
2. Click **Forgot Password**
3. Enter your registered email address
4. Check your email for the reset link
5. Create a new password

Alternatively, if you're logged in:
1. Go to **Settings > Security**
2. Enter your current password
3. Enter and confirm your new password
4. Click **Update Password**

### Can I delete my account?

Yes, you can delete your account:
1. Go to **Settings > Security**
2. Scroll to the **Danger Zone** section
3. Click **Delete Account**
4. Confirm the deletion

**Warning:** Account deletion is permanent and cannot be undone. All your data, including watchlists, alerts, and preferences, will be permanently deleted.

### Is two-factor authentication (2FA) available?

Yes, 2FA is available for all accounts:
1. Go to **Settings > Security**
2. Click **Enable 2FA**
3. Scan the QR code with your authenticator app
4. Enter the verification code to confirm

### How do I sign out of all devices?

Go to **Settings > Security > Active Sessions** to view and manage your active sessions. You can sign out of specific devices or all devices at once.

---

## Feature Questions

### What is an alpha score?

The alpha score is a proprietary metric (0-100) that indicates the potential significance of a market event. Higher scores suggest higher-conviction trading opportunities. The score combines:

- **Event type weight (35%)**: Material events like insider buys score higher
- **Sentiment (25%)**: Strong positive or negative sentiment increases score
- **Source reliability (15%)**: Official sources like SEC filings score higher
- **Recency (15%)**: More recent events score higher
- **Liquidity (10%)**: Smaller cap stocks have more alpha potential

### What does "direction" mean?

Direction indicates the expected price impact of an event:
- **BULLISH**: Likely positive price impact (green)
- **BEARISH**: Likely negative price impact (red)
- **NEUTRAL**: Unclear or no expected price impact

### How often is data updated?

Data sources are updated at different intervals:

| Source | Update Frequency |
|--------|------------------|
| SEC EDGAR | Every 10 seconds |
| PR Newswire | Every 60 seconds |
| GlobeNewswire | Every 60 seconds |
| StockTwits | Every 120 seconds |
| Reddit | Every 120 seconds |

The dashboard updates in real-time via WebSocket when connected.

### What data sources does Micro-Alpha use?

Micro-Alpha aggregates data from:
- **SEC EDGAR**: Form 4, 8-K, 13D/G filings
- **PR Newswire**: Press releases
- **GlobeNewswire**: Press releases
- **Business Wire**: Press releases
- **StockTwits**: Social sentiment
- **Reddit**: r/pennystocks and related communities

### How many tickers can I add to my watchlist?

| Plan | Watchlist Limit |
|------|-----------------|
| Starter | 10 tickers |
| Professional | Unlimited |
| Enterprise | Unlimited |

### Can I export my data?

Data export is available for Professional and Enterprise plans:
- Go to **Settings > Data Export**
- Select date range and format (CSV or JSON)
- Click **Export**

### What is the TradingView chart?

The TradingView chart on ticker detail pages is an embedded widget that provides:
- Real-time price data
- Multiple timeframes
- Technical indicators
- Drawing tools
- Full charting capabilities

Click "Open in TradingView" for the full trading platform experience.

### How do alerts work?

Alerts monitor incoming events and notify you when specific conditions are met. You can configure alerts based on:
- Specific ticker symbols
- Event types (insider trades, FDA events, etc.)
- Minimum alpha score
- Signal direction (bullish/bearish)
- Urgency level

See the [Alert Configuration Guide](./ALERT_CONFIGURATION.md) for detailed instructions.

### What's the difference between sentiment and direction?

- **Sentiment**: The tone of the text content (positive, negative, neutral), analyzed by our FinBERT ML model
- **Direction**: The expected market impact, derived from sentiment plus event type context

An event can have positive sentiment but bearish direction (e.g., "Competitor launches innovative product").

---

## Technical Questions

### What browsers are supported?

Micro-Alpha works best with modern browsers:
- Chrome (recommended)
- Firefox
- Safari
- Edge

Internet Explorer is not supported.

### Is there a mobile app?

A mobile app is currently in development. In the meantime, the web application is fully responsive and works well on mobile devices.

### Can I access Micro-Alpha via API?

Yes, API access is available for Professional and Enterprise plans:
- REST API for event data and management
- WebSocket API for real-time streaming
- API documentation available at `/api/docs`

### What does the "Live Feed Active" indicator mean?

When you see a green dot with "Live Feed Active":
- You have an active WebSocket connection
- Events will appear in real-time without refreshing
- Your connection is healthy

If you see "Disconnected":
- The WebSocket connection was lost
- Events will not update automatically
- Refresh the page to reconnect

### How is sentiment analyzed?

Micro-Alpha uses FinBERT, a BERT-based machine learning model specifically trained on financial text. It provides:
- Sentiment classification (positive, negative, neutral)
- Confidence score (0-100%)
- Optimized for financial news and SEC filings

### What is the latency for SEC filings?

SEC filings are typically captured within 15-30 seconds of publication on SEC EDGAR. This includes Form 4 (insider trades), Form 8-K (material events), and Form 13D/G (activist stakes).

### Does Micro-Alpha provide trading recommendations?

No. Micro-Alpha is an information platform that aggregates and analyzes news events. The alpha scores and sentiment analysis are informational tools, not trading recommendations. Always conduct your own research before making investment decisions.

---

## Troubleshooting

### The page is loading slowly

Try these solutions:
1. Refresh the page
2. Clear your browser cache
3. Check your internet connection
4. Try a different browser
5. Disable browser extensions

### Events are not updating in real-time

1. Check if "Live Feed Active" is shown in the header
2. If disconnected, refresh the page
3. Check your firewall settings for WebSocket connections
4. Try a different network

### I'm not receiving push notifications

1. **Check browser permissions**: Go to browser settings and ensure notifications are allowed for Micro-Alpha
2. **Check notification settings**: Go to **Settings > Notifications** and ensure "Real-time Alerts" is enabled
3. **Clear browser cache**: Sometimes cached permissions cause issues
4. **Try a different browser**: Some browsers have stricter notification policies

### My alerts are not triggering

1. **Verify alert is active**: Check the power icon is green
2. **Check conditions**: Conditions may be too restrictive
3. **Lower alpha threshold**: Try reducing minimum alpha score
4. **Expand event types**: Add more event types to match
5. **Test with all tickers**: Remove ticker filter temporarily

### The chart is not loading

1. Refresh the page
2. Disable ad blockers (may block TradingView)
3. Check that JavaScript is enabled
4. Try a different browser
5. Contact support if the issue persists

### I can't log in

1. **Check credentials**: Ensure you're using the correct email and password
2. **Reset password**: Use the "Forgot Password" link
3. **Clear cookies**: Remove Micro-Alpha cookies from browser
4. **Check email**: Look for account verification emails
5. **Contact support**: If issues persist

### Events show incorrect sentiment

Sentiment analysis is performed by machine learning models and may occasionally misclassify complex or ambiguous text. If you consistently see incorrect sentiment:
1. Note the event ID and details
2. Contact support with examples
3. We continuously improve our models based on feedback

### Search returns no results

1. **Check spelling**: Ensure ticker symbols are correct
2. **Try different terms**: Use ticker symbol instead of company name
3. **Expand date range**: Events may be outside your current filter
4. **Use simpler queries**: Break complex searches into parts

---

## Billing & Subscription

### What plans are available?

| Plan | Price | Key Features |
|------|-------|--------------|
| **Starter** | Free | Basic event feed, 3 alerts, 10 watchlist slots |
| **Professional** | $49/month | Unlimited watchlist, 25 alerts, API access, email alerts |
| **Enterprise** | Custom | Dedicated support, custom integrations, SLA, webhooks |

### How do I upgrade my plan?

1. Go to **Settings > Billing**
2. Review available plans
3. Click **Upgrade to [Plan Name]**
4. Complete payment via Stripe

### Can I downgrade my plan?

Yes, you can downgrade at any time:
1. Go to **Settings > Billing**
2. Click **Manage Subscription**
3. Select a lower tier plan
4. Changes take effect at the end of your billing period

Note: Downgrading may disable features that exceed the new plan's limits.

### What payment methods are accepted?

We accept:
- Credit cards (Visa, MasterCard, American Express)
- Debit cards
- Bank transfers (Enterprise only)

All payments are processed securely through Stripe.

### Can I get a refund?

We offer a 14-day money-back guarantee for first-time subscribers. After 14 days, subscriptions are non-refundable. Contact support@micro-alpha.com for refund requests.

### Do you offer annual billing?

Yes, annual billing is available with a 20% discount:
- Professional: $470/year (save $118)
- Contact sales for Enterprise annual pricing

### How do I cancel my subscription?

1. Go to **Settings > Billing**
2. Click **Manage Subscription**
3. Click **Cancel Subscription**
4. Confirm cancellation

Your access continues until the end of your billing period.

### Where can I find my invoices?

1. Go to **Settings > Billing**
2. Click **Manage Subscription**
3. View payment history and download invoices

---

## Data & Privacy

### What data do you collect?

We collect:
- Account information (email, name)
- Usage data (pages viewed, features used)
- Preferences (watchlist, alerts, settings)
- Device information (browser, OS)

We do not collect or store payment card information directly.

### How is my data used?

Your data is used to:
- Provide and improve the service
- Send notifications and alerts
- Analyze usage patterns
- Prevent fraud and abuse

We never sell your personal data to third parties.

### Is my data secure?

Yes, we implement industry-standard security measures:
- HTTPS encryption for all connections
- Encrypted data storage
- Regular security audits
- SOC 2 compliance (Enterprise)

### Can I request my data?

Yes, you can request a copy of your data:
1. Contact support@micro-alpha.com
2. Include your account email
3. We'll provide your data within 30 days

### What is your data retention policy?

- Active accounts: Data retained indefinitely
- Deleted accounts: Data deleted within 30 days
- Event data: Retained for 2 years
- Log data: Retained for 90 days

### Do you use cookies?

Yes, we use cookies for:
- Authentication (keeping you logged in)
- Preferences (theme, settings)
- Analytics (understanding usage)

You can manage cookie preferences in your browser settings.

### GDPR Compliance

Micro-Alpha is GDPR compliant. EU users have the right to:
- Access their data
- Correct inaccurate data
- Delete their data
- Port their data
- Object to processing

Contact privacy@micro-alpha.com for GDPR requests.

---

## Still Have Questions?

If your question isn't answered here:

1. **Check the documentation**: [User Guide](./USER_GUIDE.md) | [Alert Configuration](./ALERT_CONFIGURATION.md)
2. **Email support**: support@micro-alpha.com
3. **Response time**: Within 24 hours for all plans, 4 hours for Enterprise

---

*Last Updated: January 2026*
