from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime, timezone

import requests

from src.models.orchestrator.Reminder import Reminder
from src.persistence.ReminderStorage import ReminderStorage
from src.services.core.message_hub_service import MessageHubService

log = logging.getLogger(__name__)

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
                delivery_status = _send_sms(config.get("phone_number"), message, reminder)
            elif channel == "telegram":
                _send_telegram(config.get("chat_id"), message)
                delivery_status = "sent"
            elif channel == "teams":
                _send_teams(config.get("webhook_url"), message)
                delivery_status = "sent"
            else:
                log.warning("Unknown notification channel: %s", channel)
                continue

            any_success = True
            storage.add_reminder_history(reminder.id, delivery_status, channel=channel)
            log.info("Reminder %s %s via %s", reminder.id, delivery_status, channel)

        except Exception as e:
            tb = "".join(traceback.format_exception(e))
            log.error("Failed to send reminder %s via %s: %s", reminder.id, channel, e)
            storage.add_reminder_history(
                reminder.id, "failed", channel=channel, detail=str(e)[:500]
            )

    return any_success


def _resolve_channels(reminder: Reminder, storage: ReminderStorage) -> list[tuple[str, dict]]:
    """Return list of (channel_name, config_dict) for the reminder.

    Resolution priority:
    1. reminder.user_id → use that user's notification settings, optionally filtered
       by the user's config.default_channels list.
    2. reminder.recipient_ids → use specific notification_settings by ID.
    3. Fallback → all globally enabled settings (backwards compat only).
    """
    if reminder.user_id is not None:
        settings = storage.get_notification_settings_for_user(reminder.user_id)
        if not settings:
            log.warning("No notification settings found for user_id %s", reminder.user_id)
        return [(s.channel, s.config) for s in settings]

    # Per-reminder explicit recipient override
    if reminder.recipient_ids:
        all_settings = storage.get_notification_settings()
        ids_set = set(reminder.recipient_ids)
        result = [(s.channel, s.config) for s in all_settings if s.id in ids_set and s.enabled]
        if not result:
            log.warning("None of the requested recipient_ids %s are configured/enabled", reminder.recipient_ids)
        return result

    # Global fallback
    all_settings = storage.get_notification_settings()
    return [(s.channel, s.config) for s in all_settings if s.enabled]


def _format_message(reminder: Reminder) -> str:
    parts = [f"Reminder: {reminder.title}"]
    if reminder.message:
        parts.append(reminder.message)
    return "\n".join(parts)


def _send_sms(phone_number: str, message: str, reminder: Reminder) -> str:
    if not phone_number:
        raise ValueError("SMS phone_number not configured")

    occurrence = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    MessageHubService.instance().submit_sms(
        phone_number=phone_number,
        message=message,
        source_type="reminder",
        source_key=str(reminder.id),
        source_label="Reminders",
        user_id=reminder.user_id,
        idempotency_key=f"reminder:{reminder.id}:{occurrence}:{phone_number}",
    )
    return "queued"


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
