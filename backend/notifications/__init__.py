"""Notifications module for email and push notifications."""

from .email_service import EmailService
from .email_templates import (
    render_alert_email_html,
    render_alert_email_text,
    render_alert_subject,
)
from .notification_manager import NotificationManager

__all__ = [
    "EmailService",
    "NotificationManager",
    "render_alert_email_html",
    "render_alert_email_text",
    "render_alert_subject",
]
