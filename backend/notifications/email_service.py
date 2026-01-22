"""Email notification service using SMTP."""

import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


class EmailService:
    """Service for sending email notifications."""

    def __init__(self):
        """Initialize email service with configuration."""
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.from_email = settings.smtp_from_email
        self.from_name = settings.smtp_from_name
        self.use_tls = settings.smtp_use_tls

    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return settings.email_configured

    def _create_message(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> MIMEMultipart:
        """Create email message with HTML and optional text body.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content (optional)

        Returns:
            MIMEMultipart message
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        return msg

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> bool:
        """Send email synchronously.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content (optional)

        Returns:
            True if sent successfully
        """
        if not self.is_configured:
            logger.warning("Email not configured, skipping send", to=to_email)
            return False

        try:
            msg = self._create_message(to_email, subject, html_body, text_body)

            if self.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.host, self.port) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port) as server:
                    server.login(self.username, self.password)
                    server.send_message(msg)

            logger.info("Email sent successfully", to=to_email, subject=subject)
            return True

        except Exception as e:
            logger.error("Failed to send email", to=to_email, error=str(e))
            return False

    async def send_email_async(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> bool:
        """Send email asynchronously.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text content (optional)

        Returns:
            True if sent successfully
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.send_email(to_email, subject, html_body, text_body),
        )

    def send_alert_email(
        self,
        to_email: str,
        ticker: str,
        event_type: str,
        headline: str,
        alpha_score: float,
        direction: str,
        urgency_level: str,
        event_url: str | None = None,
    ) -> bool:
        """Send alert notification email.

        Args:
            to_email: Recipient email address
            ticker: Stock ticker symbol
            event_type: Type of event
            headline: Event headline
            alpha_score: Calculated alpha score
            direction: BULLISH/BEARISH/NEUTRAL
            urgency_level: Urgency level (critical/high/medium/low)
            event_url: Optional link to event details

        Returns:
            True if sent successfully
        """
        # Determine colors based on direction
        direction_colors = {
            "BULLISH": ("#10b981", "#065f46"),  # Green
            "BEARISH": ("#ef4444", "#991b1b"),  # Red
            "NEUTRAL": ("#6b7280", "#374151"),  # Gray
        }
        bg_color, text_color = direction_colors.get(direction, ("#6b7280", "#374151"))

        # Urgency styling
        urgency_styles = {
            "critical": "background: #ef4444; color: white;",
            "high": "background: #f97316; color: white;",
            "medium": "background: #eab308; color: black;",
            "low": "background: #6b7280; color: white;",
        }
        urgency_style = urgency_styles.get(urgency_level, urgency_styles["low"])

        subject = f"[{urgency_level.upper()}] {ticker} - {event_type}: {direction}"

        app_url = settings.app_url
        event_link = event_url or f"{app_url}/dashboard?ticker={ticker}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(to right, #1e293b, #334155); border-radius: 12px; padding: 24px; border: 1px solid #475569;">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #f8fafc; margin: 0; font-size: 24px;">News Scraper Alert</h1>
            </div>

            <!-- Alert Badge -->
            <div style="text-align: center; margin-bottom: 20px;">
                <span style="{urgency_style} padding: 6px 16px; border-radius: 9999px; font-size: 12px; font-weight: 600; text-transform: uppercase;">
                    {urgency_level} Priority
                </span>
            </div>

            <!-- Main Content Card -->
            <div style="background: #0f172a; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <!-- Ticker & Direction -->
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div>
                        <span style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Ticker</span>
                        <h2 style="color: #f8fafc; margin: 4px 0 0 0; font-size: 28px; font-weight: bold;">${ticker}</h2>
                    </div>
                    <div style="text-align: right;">
                        <span style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Signal</span>
                        <div style="background: {bg_color}; color: white; padding: 8px 16px; border-radius: 6px; font-weight: bold; margin-top: 4px;">
                            {direction}
                        </div>
                    </div>
                </div>

                <!-- Event Type -->
                <div style="margin-bottom: 16px;">
                    <span style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Event Type</span>
                    <p style="color: #e2e8f0; margin: 4px 0 0 0; font-size: 16px;">{event_type.replace('_', ' ').title()}</p>
                </div>

                <!-- Headline -->
                <div style="margin-bottom: 16px;">
                    <span style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Headline</span>
                    <p style="color: #f8fafc; margin: 4px 0 0 0; font-size: 16px; line-height: 1.5;">{headline}</p>
                </div>

                <!-- Alpha Score -->
                <div style="background: #1e293b; border-radius: 6px; padding: 16px; text-align: center;">
                    <span style="color: #94a3b8; font-size: 12px; text-transform: uppercase;">Alpha Score</span>
                    <div style="color: {bg_color}; font-size: 32px; font-weight: bold; margin-top: 4px;">
                        {alpha_score:.2f}
                    </div>
                </div>
            </div>

            <!-- CTA Button -->
            <div style="text-align: center;">
                <a href="{event_link}" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 32px; border-radius: 6px; text-decoration: none; font-weight: 600;">
                    View Details
                </a>
            </div>

            <!-- Footer -->
            <div style="text-align: center; margin-top: 24px; padding-top: 20px; border-top: 1px solid #334155;">
                <p style="color: #64748b; font-size: 12px; margin: 0;">
                    This alert was triggered by your configured alert rules.<br>
                    <a href="{app_url}/settings/alerts" style="color: #3b82f6; text-decoration: none;">Manage alert settings</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""

        text_body = f"""
News Scraper Alert - {urgency_level.upper()} PRIORITY

Ticker: ${ticker}
Signal: {direction}
Event Type: {event_type.replace('_', ' ').title()}
Alpha Score: {alpha_score:.2f}

Headline:
{headline}

View details: {event_link}

---
This alert was triggered by your configured alert rules.
Manage settings: {app_url}/settings/alerts
"""

        return self.send_email(to_email, subject, html_body, text_body)

    def send_daily_digest(
        self,
        to_email: str,
        user_name: str,
        events: list[dict[str, Any]],
        watchlist_summary: dict[str, Any],
    ) -> bool:
        """Send daily digest email.

        Args:
            to_email: Recipient email address
            user_name: User's name
            events: List of notable events
            watchlist_summary: Summary of watchlist activity

        Returns:
            True if sent successfully
        """
        subject = f"Daily Digest - {len(events)} Notable Events"
        app_url = settings.app_url

        events_html = ""
        for event in events[:10]:
            direction_color = "#10b981" if event.get("direction") == "BULLISH" else "#ef4444"
            events_html += f"""
            <tr style="border-bottom: 1px solid #334155;">
                <td style="padding: 12px; color: #f8fafc; font-weight: bold;">${event.get('ticker', 'N/A')}</td>
                <td style="padding: 12px; color: #e2e8f0;">{event.get('headline', '')[:50]}...</td>
                <td style="padding: 12px; color: {direction_color}; font-weight: bold;">{event.get('direction', 'N/A')}</td>
                <td style="padding: 12px; color: #e2e8f0;">{event.get('alpha_score', 0):.2f}</td>
            </tr>
            """

        html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background-color: #0f172a;">
    <div style="max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #475569;">
            <h1 style="color: #f8fafc; margin: 0 0 8px 0;">Good morning{', ' + user_name if user_name else ''}!</h1>
            <p style="color: #94a3b8; margin: 0 0 24px 0;">Here's your daily market intelligence digest.</p>

            <h2 style="color: #f8fafc; font-size: 18px; margin: 0 0 16px 0;">Top Events</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 2px solid #475569;">
                        <th style="text-align: left; padding: 12px; color: #94a3b8; font-size: 12px;">TICKER</th>
                        <th style="text-align: left; padding: 12px; color: #94a3b8; font-size: 12px;">HEADLINE</th>
                        <th style="text-align: left; padding: 12px; color: #94a3b8; font-size: 12px;">SIGNAL</th>
                        <th style="text-align: left; padding: 12px; color: #94a3b8; font-size: 12px;">ALPHA</th>
                    </tr>
                </thead>
                <tbody>
                    {events_html if events_html else '<tr><td colspan="4" style="padding: 24px; color: #94a3b8; text-align: center;">No notable events in the last 24 hours</td></tr>'}
                </tbody>
            </table>

            <div style="text-align: center; margin-top: 24px;">
                <a href="{app_url}/dashboard" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 32px; border-radius: 6px; text-decoration: none; font-weight: 600;">
                    View Full Dashboard
                </a>
            </div>
        </div>
    </div>
</body>
</html>
"""

        return self.send_email(to_email, subject, html_body)


# Global instance
email_service = EmailService()
