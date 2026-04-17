from __future__ import annotations

import logging
import os
import traceback

import requests

from src.models.orchestrator.Reminder import Reminder
from src.persistence.ReminderStorage import ReminderStorage

log = logging.getLogger(__name__)

SMS_BOT_URL = os.environ.get("SMS_BOT_URL", "http://sms-hub:5050")
TELEGRAM_BOT_URL = os.environ.get("TELEGRAM_BOT_URL", "http://overlia-power-bot:5060")

_TIMEOUT = (5, 15)


def dispatch_reminder(reminder: Reminder) -> bool:
    """Send a reminder notification to all configured channels.

    Returns True if at least one channel was sent successfully.
    """
    storage = ReminderStorage()
    channels = _resolve_channels(reminder, storage)

    if not channels:
        log.warning("No notification channels configured for reminder %s", reminder.id)
        storage.add_reminder_history(reminder.id, "failed", detail="No channels configured")
        return False

    message = _format_message(reminder)
    any_success = False

    for channel, config in channels:
        try:
            if channel == "sms":
                _send_sms(config.get("phone_number"), message)
            elif channel == "telegram":
                _send_telegram(config.get("chat_id"), message)
            elif channel == "teams":
                _send_teams(config.get("webhook_url"), message)
            else:
                log.warning("Unknown notification channel: %s", channel)
                continue

            any_success = True
            storage.add_reminder_history(reminder.id, "sent", channel=channel)
            log.info("Reminder %s sent via %s", reminder.id, channel)

        except Exception as e:
            tb = "".join(traceback.format_exception(e))
            log.error("Failed to send reminder %s via %s: %s", reminder.id, channel, e)
            storage.add_reminder_history(
                reminder.id, "failed", channel=channel, detail=str(e)[:500]
            )

    return any_success


def _resolve_channels(reminder: Reminder, storage: ReminderStorage) -> list[tuple[str, dict]]:
    """Return list of (channel_name, config_dict) for the reminder."""
    settings = storage.get_notification_settings()

    if reminder.recipient_ids:
        # Per-reminder override: only use the specific notification settings
        ids_set = set(reminder.recipient_ids)
        result = [(s.channel, s.config) for s in settings if s.id in ids_set and s.enabled]
        if not result:
            log.warning("None of the requested recipient_ids %s are configured/enabled", reminder.recipient_ids)
        return result
    else:
        # Use global defaults: all enabled entries (multiple users per channel)
        return [(s.channel, s.config) for s in settings if s.enabled]


def _format_message(reminder: Reminder) -> str:
    parts = [f"Reminder: {reminder.title}"]
    if reminder.message:
        parts.append(reminder.message)
    return "\n".join(parts)


def _send_sms(phone_number: str, message: str) -> None:
    if not phone_number:
        raise ValueError("SMS phone_number not configured")

    resp = requests.post(
        f"{SMS_BOT_URL}/api/sms/send",
        json={"phone": phone_number, "message": message},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


def _send_telegram(chat_id, message: str) -> None:
    if not chat_id:
        raise ValueError("Telegram chat_id not configured")

    resp = requests.post(
        f"{TELEGRAM_BOT_URL}/api/telegram/send",
        json={"chat_id": chat_id, "message": message},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


def _send_teams(webhook_url: str, message: str) -> None:
    if not webhook_url:
        raise ValueError("Teams webhook_url not configured")

    resp = requests.post(webhook_url, json={"text": message}, timeout=_TIMEOUT)
    resp.raise_for_status()
