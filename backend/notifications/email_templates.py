"""Email templates for alert notifications."""

from datetime import datetime
from typing import Any

from backend.config import settings


def get_base_styles() -> str:
    """Get base CSS styles for email templates."""
    return """
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            line-height: 1.6;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 24px;
        }
        .card {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            border-radius: 16px;
            padding: 32px;
            border: 1px solid #475569;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid #475569;
        }
        .logo {
            font-size: 28px;
            font-weight: 700;
            color: #f8fafc;
            margin: 0;
        }
        .logo-accent {
            color: #3b82f6;
        }
        .badge {
            display: inline-block;
            padding: 6px 16px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .badge-critical { background: #ef4444; color: white; }
        .badge-high { background: #f97316; color: white; }
        .badge-medium { background: #eab308; color: #1e293b; }
        .badge-low { background: #6b7280; color: white; }
        .content-card {
            background: #0f172a;
            border-radius: 12px;
            padding: 24px;
            margin: 20px 0;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        .metric {
            flex: 1;
        }
        .metric-label {
            color: #94a3b8;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }
        .metric-value {
            color: #f8fafc;
            font-size: 16px;
            font-weight: 600;
        }
        .ticker {
            font-size: 36px;
            font-weight: 800;
            color: #f8fafc;
            margin: 0;
        }
        .direction-bullish { color: #10b981; }
        .direction-bearish { color: #ef4444; }
        .direction-neutral { color: #94a3b8; }
        .alpha-score {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid #334155;
        }
        .alpha-value {
            font-size: 48px;
            font-weight: 800;
            margin: 8px 0;
        }
        .headline {
            color: #f8fafc;
            font-size: 18px;
            line-height: 1.5;
            margin: 16px 0;
        }
        .cta-button {
            display: inline-block;
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            padding: 14px 32px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            margin-top: 16px;
        }
        .footer {
            text-align: center;
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid #334155;
        }
        .footer-text {
            color: #64748b;
            font-size: 12px;
            margin: 0;
        }
        .footer-link {
            color: #3b82f6;
            text-decoration: none;
        }
    """


def get_direction_color(direction: str) -> str:
    """Get color for direction indicator."""
    colors = {
        "BULLISH": "#10b981",
        "BEARISH": "#ef4444",
        "NEUTRAL": "#94a3b8",
    }
    return colors.get(direction.upper() if direction else "NEUTRAL", "#94a3b8")


def get_urgency_badge_class(urgency: str) -> str:
    """Get badge class for urgency level."""
    return f"badge-{urgency.lower()}" if urgency else "badge-low"


def render_alert_email_html(
    ticker: str,
    headline: str,
    event_type: str,
    sentiment_label: str | None,
    alpha_score: float,
    direction: str,
    urgency_level: str,
    event_id: str | None = None,
    source_name: str | None = None,
    event_time: datetime | None = None,
) -> str:
    """Render professional HTML email template for alert notification.

    Args:
        ticker: Stock ticker symbol
        headline: Event headline
        event_type: Type of event (e.g., "INSIDER_TRADE", "SEC_FILING")
        sentiment_label: Sentiment classification (positive/negative/neutral)
        alpha_score: Calculated alpha score
        direction: Signal direction (BULLISH/BEARISH/NEUTRAL)
        urgency_level: Urgency level (critical/high/medium/low)
        event_id: Optional event ID for deep linking
        source_name: Source of the event
        event_time: Time of the event

    Returns:
        Rendered HTML string
    """
    app_url = settings.app_url
    direction_color = get_direction_color(direction)
    urgency_class = get_urgency_badge_class(urgency_level)

    # Format event type for display
    event_type_display = event_type.replace("_", " ").title() if event_type else "Event"

    # Build event link
    event_link = f"{app_url}/events/{event_id}" if event_id else f"{app_url}/dashboard?ticker={ticker}"

    # Format time
    time_display = event_time.strftime("%B %d, %Y at %I:%M %p UTC") if event_time else "Just now"

    # Sentiment display
    sentiment_display = sentiment_label.title() if sentiment_label else "N/A"

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Alert: {ticker} - {event_type_display}</title>
    <style>
        {get_base_styles()}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <!-- Header -->
            <div class="header">
                <h1 class="logo">News<span class="logo-accent">Scraper</span></h1>
                <p style="color: #94a3b8; margin: 8px 0 0 0; font-size: 14px;">Market Intelligence Alert</p>
            </div>

            <!-- Urgency Badge -->
            <div style="text-align: center; margin-bottom: 24px;">
                <span class="badge {urgency_class}">
                    {urgency_level.upper() if urgency_level else 'LOW'} PRIORITY
                </span>
            </div>

            <!-- Main Content -->
            <div class="content-card">
                <!-- Ticker & Direction Row -->
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px;">
                    <div>
                        <div class="metric-label">Ticker Symbol</div>
                        <h2 class="ticker">${ticker}</h2>
                    </div>
                    <div style="text-align: right;">
                        <div class="metric-label">Signal</div>
                        <div style="background: {direction_color}; color: white; padding: 10px 20px; border-radius: 8px; font-weight: 700; font-size: 16px; margin-top: 4px;">
                            {direction if direction else 'NEUTRAL'}
                        </div>
                    </div>
                </div>

                <!-- Event Details -->
                <div style="margin-bottom: 20px;">
                    <div class="metric-label">Event Type</div>
                    <div class="metric-value">{event_type_display}</div>
                </div>

                <div style="margin-bottom: 20px;">
                    <div class="metric-label">Headline</div>
                    <p class="headline">{headline}</p>
                </div>

                <!-- Metrics Row -->
                <div style="display: flex; gap: 16px; margin-bottom: 20px;">
                    <div style="flex: 1; background: #1e293b; padding: 16px; border-radius: 8px;">
                        <div class="metric-label">Sentiment</div>
                        <div class="metric-value" style="color: {direction_color};">{sentiment_display}</div>
                    </div>
                    <div style="flex: 1; background: #1e293b; padding: 16px; border-radius: 8px;">
                        <div class="metric-label">Source</div>
                        <div class="metric-value">{source_name if source_name else 'N/A'}</div>
                    </div>
                </div>

                <!-- Alpha Score -->
                <div class="alpha-score">
                    <div class="metric-label">Alpha Score</div>
                    <div class="alpha-value" style="color: {direction_color};">
                        {alpha_score:.2f if alpha_score is not None else 'N/A'}
                    </div>
                    <div style="color: #64748b; font-size: 12px;">
                        Calculated trading signal strength
                    </div>
                </div>
            </div>

            <!-- Event Time -->
            <div style="text-align: center; color: #94a3b8; font-size: 13px; margin-bottom: 20px;">
                Event detected: {time_display}
            </div>

            <!-- CTA Button -->
            <div style="text-align: center;">
                <a href="{event_link}" class="cta-button" style="color: white;">
                    View Full Details
                </a>
            </div>

            <!-- Footer -->
            <div class="footer">
                <p class="footer-text">
                    This alert was triggered by your configured alert rules.<br>
                    <a href="{app_url}/settings/alerts" class="footer-link">Manage your alert preferences</a>
                    &nbsp;|&nbsp;
                    <a href="{app_url}/unsubscribe" class="footer-link">Unsubscribe</a>
                </p>
                <p class="footer-text" style="margin-top: 12px;">
                    &copy; {datetime.now().year} News Scraper. All rights reserved.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def render_alert_email_text(
    ticker: str,
    headline: str,
    event_type: str,
    sentiment_label: str | None,
    alpha_score: float,
    direction: str,
    urgency_level: str,
    event_id: str | None = None,
    source_name: str | None = None,
    event_time: datetime | None = None,
) -> str:
    """Render plain text email for alert notification.

    Args:
        ticker: Stock ticker symbol
        headline: Event headline
        event_type: Type of event
        sentiment_label: Sentiment classification
        alpha_score: Calculated alpha score
        direction: Signal direction
        urgency_level: Urgency level
        event_id: Optional event ID for deep linking
        source_name: Source of the event
        event_time: Time of the event

    Returns:
        Plain text email content
    """
    app_url = settings.app_url
    event_type_display = event_type.replace("_", " ").title() if event_type else "Event"
    event_link = f"{app_url}/events/{event_id}" if event_id else f"{app_url}/dashboard?ticker={ticker}"
    time_display = event_time.strftime("%B %d, %Y at %I:%M %p UTC") if event_time else "Just now"

    return f"""
================================================================================
                        NEWS SCRAPER ALERT
================================================================================

                    [{urgency_level.upper() if urgency_level else 'LOW'} PRIORITY]

--------------------------------------------------------------------------------
TICKER: ${ticker}
SIGNAL: {direction if direction else 'NEUTRAL'}
--------------------------------------------------------------------------------

EVENT TYPE: {event_type_display}

HEADLINE:
{headline}

--------------------------------------------------------------------------------
METRICS
--------------------------------------------------------------------------------
Alpha Score:    {alpha_score:.2f if alpha_score is not None else 'N/A'}
Sentiment:      {sentiment_label.title() if sentiment_label else 'N/A'}
Source:         {source_name if source_name else 'N/A'}
Detected:       {time_display}

--------------------------------------------------------------------------------

View full details: {event_link}

================================================================================

This alert was triggered by your configured alert rules.
Manage preferences: {app_url}/settings/alerts
Unsubscribe: {app_url}/unsubscribe

(c) {datetime.now().year} News Scraper. All rights reserved.
"""


def render_alert_subject(
    ticker: str,
    event_type: str,
    direction: str,
    urgency_level: str,
) -> str:
    """Generate email subject line for alert.

    Args:
        ticker: Stock ticker symbol
        event_type: Type of event
        direction: Signal direction
        urgency_level: Urgency level

    Returns:
        Email subject line
    """
    event_type_short = event_type.replace("_", " ").title() if event_type else "Event"

    # Use emoji indicators for visual distinction (most email clients support these)
    direction_indicator = {
        "BULLISH": "^",
        "BEARISH": "v",
        "NEUTRAL": "-",
    }.get(direction.upper() if direction else "NEUTRAL", "-")

    urgency_prefix = ""
    if urgency_level:
        if urgency_level.lower() == "critical":
            urgency_prefix = "[CRITICAL] "
        elif urgency_level.lower() == "high":
            urgency_prefix = "[HIGH] "

    return f"{urgency_prefix}${ticker} {direction_indicator} {event_type_short}: {direction if direction else 'NEUTRAL'}"
