import asyncio
import datetime
import logging
import re
from functools import wraps
from zoneinfo import ZoneInfo

import dateparser
from telegram import ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from src.apis.core import HuginCoreClient
from src.apis.orchestrator import OrchestratorClient
from src.config import settings

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("Europe/Oslo")

core = HuginCoreClient(settings.CORE_API_URL)
orchestrator = OrchestratorClient()


def restricted(command_path: str = None):
    """Resolve the Telegram user against the orchestrator user database.
    Rejects senders not linked to any user. Optionally checks command_path against allowed_commands.
    Stores resolved user in context.

    Usage:
        @restricted()                        — identity check only (admin-like commands)
        @restricted('telegram/chart')        — identity + permission check
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            telegram_user_id = str(update.effective_user.id) if update.effective_user else None
            if not telegram_user_id:
                return

            user = orchestrator.lookup_user(channel='telegram', identifier=telegram_user_id)
            if user is None:
                logger.warning("Unknown Telegram user_id %s. Rejecting.", telegram_user_id)
                if update.message:
                    await update.message.reply_text("Unknown user. Contact admin.")
                elif update.callback_query:
                    await update.callback_query.answer("Unknown user. Contact admin.", show_alert=True)
                return

            # Permission check for non-admin users
            if command_path and not user.get('is_admin'):
                allowed = user.get('allowed_commands')
                if allowed is None or command_path not in allowed:
                    logger.warning("User %s denied for command %s", telegram_user_id, command_path)
                    if update.message:
                        await update.message.reply_text("Permission denied.")
                    elif update.callback_query:
                        await update.callback_query.answer("Permission denied.", show_alert=True)
                    return

            context.user_data['resolved_user'] = user
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


def _get_user_label(update: Update) -> str:
    """Derive a human-readable label from the Telegram user."""
    user = update.effective_user
    return user.first_name or user.username or str(user.id)


@restricted()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


@restricted()
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Help!")


@restricted('telegram/data')
async def total_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = core.get_growatt_data()
    if not data:
        await update.message.reply_text("error")
        return

    data.pop("isHaveStorage", None)
    data.pop("plantId", None)
    data.pop("plantMoneyText", None)
    data.pop("plantName", None)

    formatted_dict = "\n".join(f"{key}: {value}" for key, value in data.items())
    await update.message.reply_text(formatted_dict)


@restricted('telegram/deye')
async def deye_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = core.get_deye_data()
    if not data:
        await update.message.reply_text("Could not fetch Deye data.")
        return

    formatted_dict = "\n".join(f"{key}: {value}" for key, value in data.items())
    await update.message.reply_text(formatted_dict)


@restricted('telegram/weather')
async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        name = " ".join(context.args)
        target_user = orchestrator.get_user_by_name(name)
        if target_user is None:
            await update.message.reply_text(f"User not found: {name}")
            return
        location_id = (target_user.get('config') or {}).get('weather_location_id', '')
        if not location_id:
            display = target_user.get('display_name') or target_user.get('username') or name
            await update.message.reply_text(f"{display}'s weather location is not configured.")
            return
    else:
        user = context.user_data.get('resolved_user', {})
        location_id = (user.get('config') or {}).get('weather_location_id', '')
        if not location_id:
            await update.message.reply_text("Weather location not configured. Set it in your profile settings.")
            return
    image = core.get_weather_image(location_id)
    if image is None:
        await update.message.reply_text("Could not fetch weather.")
        return
    await update.message.reply_photo(image)


@restricted('telegram/nikolai_weather')
async def nikolai_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nikolai_telegram_id = settings.NIKOLAI_TELEGRAM_ID
    if not nikolai_telegram_id:
        await update.message.reply_text("NIKOLAI_TELEGRAM_ID is not configured.")
        return
    nikolai_user = orchestrator.lookup_user(channel='telegram', identifier=nikolai_telegram_id)
    if nikolai_user is None:
        await update.message.reply_text("Could not find Nikolai's user account.")
        return
    location_id = (nikolai_user.get('config') or {}).get('weather_location_id', '')
    if not location_id:
        await update.message.reply_text("Nikolai's weather location is not configured.")
        return
    image = core.get_weather_image(location_id)
    if image is None:
        await update.message.reply_text("Could not fetch weather.")
        return
    await update.message.reply_photo(image)


@restricted('telegram/chart')
async def get_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    image = core.get_daily_chart()
    if image is None:
        await update.message.reply_text("Could not generate chart.")
        return
    await update.message.reply_photo(image)


@restricted('telegram/chartdays')
async def get_chart_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.split(" ")
    if len(text) == 1:
        image = core.get_multiday_chart(7)
        if image is None:
            await update.message.reply_text("Could not generate chart.")
            return
        await update.message.reply_photo(image)
        return
    elif len(text) > 2:
        await update.message.reply_text("Please provide only one number")
        return

    if text[1].isdigit():
        if int(text[1]) > 7:
            await update.message.reply_text("Please provide a number less or equal to 7")
            return
        image = core.get_multiday_chart(int(text[1]))
        if image is None:
            await update.message.reply_text("Could not generate chart.")
            return
        await update.message.reply_photo(image)
    else:
        await update.message.reply_text("Please provide a valid number")


@restricted('telegram/nikolai_power')
async def nikolai_power(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = core.get_current_power()
    if not data or "error" in data:
        await update.message.reply_text("Could not fetch current power.")
        return
    text = (
        f"PV1: {data.get('pv1_power', 'N/A')} W\n"
        f"PV2: {data.get('pv2_power', 'N/A')} W\n"
        f"Grid: {data.get('grid_power', 'N/A')} W\n"
        f"Grid status: {data.get('grid_status', 'N/A')}\n"
        f"Recorded at: {data.get('recorded_at', 'N/A')}"
    )
    await update.message.reply_text(text)



@restricted('telegram/nikolai_energytoday')
async def nikolai_energytoday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = core.get_today_energy()
    if not data:
        await update.message.reply_text("Could not fetch today's energy.")
        return
    text = (
        f"Date: {data.get('date', 'N/A')}\n"
        f"PV1: {data.get('pv1_energy_wh', 0)} Wh\n"
        f"PV2: {data.get('pv2_energy_wh', 0)} Wh\n"
        f"Total: {data.get('total_energy_wh', 0)} Wh\n"
        f"Grid: {data.get('grid_energy_wh', 0)} Wh\n"
        f"Readings: {data.get('reading_count', 0)}"
    )
    await update.message.reply_text(text)


@restricted('telegram/nikolai_energyhour')
async def nikolai_energyhour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = core.get_last_hour_energy()
    if not data:
        await update.message.reply_text("Could not fetch last hour energy.")
        return
    text = (
        f"Period: last hour\n"
        f"PV1: {data.get('pv1_energy_wh', 0)} Wh\n"
        f"PV2: {data.get('pv2_energy_wh', 0)} Wh\n"
        f"Total: {data.get('total_energy_wh', 0)} Wh\n"
        f"Grid: {data.get('grid_energy_wh', 0)} Wh\n"
        f"Readings: {data.get('reading_count', 0)}"
    )
    await update.message.reply_text(text)



@restricted('telegram/chartmonth')
async def get_chart_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.split(" ")
    if len(text) == 1:
        now = datetime.datetime.now()
        image = core.get_monthly_chart(now.month, now.year)
        if image is None:
            await update.message.reply_text("Could not generate chart.")
            return
        await update.message.reply_photo(image)
        return
    elif len(text) > 3:
        await update.message.reply_text("Please provide up to two numbers")
        return

    if not text[1].isdigit():
        await update.message.reply_text("Please provide a valid number")
        return

    month = int(text[1])
    if month < 1 or month > 12:
        await update.message.reply_text("Please provide a number between 1 and 12")
        return

    if len(text) == 3:
        if not text[2].isdigit():
            await update.message.reply_text("Please provide a valid number")
            return
        year = int(text[2])
        if year > datetime.datetime.now().year:
            await update.message.reply_text("Please provide a number less or equal to the current year")
            return
        image = core.get_monthly_chart(month, year)
        if image is None:
            await update.message.reply_text("Could not generate chart.")
            return
        await update.message.reply_photo(image)
        return

    image = core.get_monthly_chart(month, datetime.datetime.now().year)
    if image is None:
        await update.message.reply_text("Could not generate chart.")
        return
    await update.message.reply_photo(image)


# ── Reminder Commands ─────────────────────────────────────


@restricted('telegram/remind')
async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a reminder: /remind 45m check the oven"""
    text = update.message.text.split(None, 2)
    if len(text) < 2:
        await update.message.reply_text("Usage: /remind <when> <message>\nExample: /remind 45m check the oven")
        return

    time_string = text[1]
    message = text[2] if len(text) > 2 else "Reminder"

    parsed_time = dateparser.parse(time_string)
    if not parsed_time:
        await update.message.reply_text(f"Could not parse time '{time_string}'. Try: 45m, 2h, tomorrow 3pm")
        return

    result = orchestrator.create_reminder(
        title=message,
        due_at=parsed_time.isoformat(),
        created_by="telegram",
        user_id=(context.user_data.get('resolved_user') or {}).get('id'),
    )

    if result is None:
        await update.message.reply_text("Failed to create reminder.")
        return

    rid = result.get("id", "?")
    display_time = parsed_time.astimezone(_TZ).strftime('%Y-%m-%d %H:%M')
    await update.message.reply_text(
        f"✅ Reminder #{rid} set for {display_time}: {message}"
    )


@restricted('telegram/reminders')
async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active reminders: /reminders"""
    reminders = orchestrator.list_reminders(
        status="active",
        user_id=(context.user_data.get('resolved_user') or {}).get('id'),
    )
    if reminders is None:
        await update.message.reply_text("Failed to fetch reminders.")
        return

    if not reminders:
        await update.message.reply_text("No active reminders.")
        return

    lines = []
    for r in reminders[:15]:
        due = r.get("due_at", "?")
        if isinstance(due, str) and "T" in due:
            due = due[:16].replace("T", " ")
        lines.append(f"#{r['id']} {due} — {r['title']}")

    await update.message.reply_text("Active reminders:\n" + "\n".join(lines))


@restricted('telegram/snooze')
async def snooze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Snooze a reminder: /snooze 1 10m"""
    text = update.message.text.split()
    if len(text) < 2:
        await update.message.reply_text("Usage: /snooze <id> [duration]\nExample: /snooze 1 10m")
        return

    try:
        reminder_id = int(text[1])
    except ValueError:
        await update.message.reply_text("Invalid reminder ID.")
        return

    duration = text[2] if len(text) > 2 else "10m"
    result = orchestrator.snooze_reminder(reminder_id, duration)

    if result is None:
        await update.message.reply_text("Failed to snooze reminder.")
        return

    due = result.get("due_at", "?")
    if isinstance(due, str) and "T" in due:
        due = due[:16].replace("T", " ")
    await update.message.reply_text(f"Reminder #{reminder_id} snoozed until {due}")


@restricted('telegram/dismiss')
async def dismiss_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dismiss a reminder: /dismiss 1"""
    text = update.message.text.split()
    if len(text) < 2:
        await update.message.reply_text("Usage: /dismiss <id>")
        return

    try:
        reminder_id = int(text[1])
    except ValueError:
        await update.message.reply_text("Invalid reminder ID.")
        return

    result = orchestrator.dismiss_reminder(reminder_id)
    if result is None:
        await update.message.reply_text("Failed to dismiss reminder.")
        return

    await update.message.reply_text(f"Reminder #{reminder_id} dismissed.")


@restricted('telegram/register')
async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register this chat for Telegram notifications: /register"""
    chat_id = update.effective_chat.id
    user_label = _get_user_label(update)
    resolved_user = context.user_data.get('resolved_user')
    result = orchestrator.update_notification_setting(
        channel="telegram",
        enabled=True,
        config={"chat_id": chat_id},
        user_label=user_label,
        user_id=resolved_user.get('id') if resolved_user else None,
    )

    if result is None:
        await update.message.reply_text("Failed to register. Is the orchestrator running?")
        return

    await update.message.reply_text(f"✅ Telegram notifications registered for {user_label}")


@restricted('telegram/registerphone')
async def registerphone_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register a phone number for SMS notifications: /registerphone +4712345678"""
    text = update.message.text.split()
    if len(text) < 2:
        await update.message.reply_text("Usage: /registerphone <phone>\nExample: /registerphone +4712345678")
        return

    phone = text[1]
    if not re.match(r'^\+\d{7,15}$', phone):
        await update.message.reply_text("Invalid phone number. Use international format: +4712345678")
        return

    user_label = _get_user_label(update)
    result = orchestrator.update_notification_setting(
        channel="sms",
        enabled=True,
        config={"phone_number": phone},
        user_label=user_label,
    )

    if result is None:
        await update.message.reply_text("Failed to register phone. Is the orchestrator running?")
        return

    await update.message.reply_text(f"✅ SMS notifications registered for {user_label} ({phone})")


@restricted()
async def reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses for snooze/dismiss."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data:
        return

    parts = data.split(":")
    if len(parts) < 2:
        return

    action = parts[0]
    try:
        reminder_id = int(parts[1])
    except ValueError:
        return

    if action == "snooze":
        duration = parts[2] if len(parts) > 2 else "10m"
        result = orchestrator.snooze_reminder(reminder_id, duration)
        if result:
            due = result.get("due_at", "?")
            if isinstance(due, str) and "T" in due:
                due = due[:16].replace("T", " ")
            await query.edit_message_text(f"Snoozed until {due}")
        else:
            await query.edit_message_text("Failed to snooze.")
    elif action == "dismiss":
        result = orchestrator.dismiss_reminder(reminder_id)
        if result:
            await query.edit_message_text("Dismissed.")
        else:
            await query.edit_message_text("Failed to dismiss.")


async def _post_init(application: Application) -> None:
    """Capture the running event loop so the Flask API thread can schedule sends into it."""
    import src.api.telegram_api as telegram_api
    telegram_api.set_app_loop(asyncio.get_running_loop())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=context.error)


def main() -> None:
    application = Application.builder().token(settings.TELEGRAM_API_KEY).post_init(_post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("data", total_data_command))
    application.add_handler(CommandHandler("deye", deye_command))
    application.add_handler(CommandHandler("weather", get_weather))
    application.add_handler(CommandHandler("nikolai_weather", nikolai_weather))
    application.add_handler(CommandHandler("chart", get_chart))
    application.add_handler(CommandHandler("chartdays", get_chart_days))
    application.add_handler(CommandHandler("chartmonth", get_chart_month))
    application.add_handler(CommandHandler("nikolai_power", nikolai_power))
    application.add_handler(CommandHandler("nikolai_energytoday", nikolai_energytoday))
    application.add_handler(CommandHandler("nikolai_energyhour", nikolai_energyhour))

    # Reminder commands
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("snooze", snooze_command))
    application.add_handler(CommandHandler("dismiss", dismiss_command))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("registerphone", registerphone_command))
    application.add_handler(CallbackQueryHandler(reminder_callback))
    application.add_error_handler(error_handler)

    # Start the outbound Telegram REST API in a background thread
    from src.api.telegram_api import start_api_server
    start_api_server(application.bot)

    application.run_polling(allowed_updates=Update.ALL_TYPES)
