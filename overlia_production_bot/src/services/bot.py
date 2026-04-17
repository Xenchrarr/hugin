import datetime
import logging
import re
from functools import wraps

import dateparser
from telegram import ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from src.apis.core import HuginCoreClient
from src.apis.orchestrator import OrchestratorClient
from src.config import settings

logger = logging.getLogger(__name__)

core = HuginCoreClient(settings.CORE_API_URL)
orchestrator = OrchestratorClient()


def restricted(func):
    """Block users not in ALLOWED_USER_IDS. Empty set = allow all."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if settings.ALLOWED_USER_IDS and update.effective_user.id not in settings.ALLOWED_USER_IDS:
            logger.warning("Unauthorized access attempt by user %s", update.effective_user.id)
            if update.message:
                await update.message.reply_text("Unauthorized.")
            elif update.callback_query:
                await update.callback_query.answer("Unauthorized.", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def _get_user_label(update: Update) -> str:
    """Derive a human-readable label from the Telegram user."""
    user = update.effective_user
    return user.first_name or user.username or str(user.id)


@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Help!")


@restricted
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


@restricted
async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    image = core.get_weather_image(settings.YR_ID)
    if image is None:
        await update.message.reply_text("Could not fetch weather.")
        return
    await update.message.reply_photo(image)


@restricted
async def nikolai_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    image = core.get_weather_image(settings.NIKOLAI_YR_ID)
    if image is None:
        await update.message.reply_text("Could not fetch weather.")
        return
    await update.message.reply_photo(image)


@restricted
async def get_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    image = core.get_daily_chart()
    if image is None:
        await update.message.reply_text("Could not generate chart.")
        return
    await update.message.reply_photo(image)


@restricted
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


@restricted
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


@restricted
async def nikolai_powerhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hours = 1.0
    text = update.message.text.split(" ")
    if len(text) > 1:
        try:
            hours = float(text[1])
            if hours < 0.1 or hours > 168:
                await update.message.reply_text("Hours must be between 0.1 and 168.")
                return
        except ValueError:
            await update.message.reply_text("Please provide a valid number of hours.")
            return

    data = core.get_power_history(hours)
    if not data or not data.get("readings"):
        await update.message.reply_text("No power history available.")
        return

    image = core.get_power_history_chart(hours)
    if image is None:
        await update.message.reply_text("Could not generate chart.")
        return
    await update.message.reply_photo(image)


@restricted
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


@restricted
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


@restricted
async def nikolai_energydaily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    days = 30
    text = update.message.text.split(" ")
    if len(text) > 1:
        if text[1].isdigit():
            days = int(text[1])
            if days < 1 or days > 365:
                await update.message.reply_text("Days must be between 1 and 365.")
                return
        else:
            await update.message.reply_text("Please provide a valid number of days.")
            return

    data = core.get_daily_energy(days)
    if not data or not data.get("days"):
        await update.message.reply_text("No daily energy data available.")
        return

    image = core.get_daily_energy_chart(days)
    if image is None:
        await update.message.reply_text("Could not generate chart.")
        return
    await update.message.reply_photo(image)


@restricted
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


@restricted
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
    )

    if result is None:
        await update.message.reply_text("Failed to create reminder.")
        return

    rid = result.get("id", "?")
    await update.message.reply_text(
        f"✅ Reminder #{rid} set for {parsed_time.strftime('%Y-%m-%d %H:%M')}: {message}"
    )


@restricted
async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active reminders: /reminders"""
    reminders = orchestrator.list_reminders(status="active")
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


@restricted
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


@restricted
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


@restricted
async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register this chat for Telegram notifications: /register"""
    chat_id = update.effective_chat.id
    user_label = _get_user_label(update)
    result = orchestrator.update_notification_setting(
        channel="telegram",
        enabled=True,
        config={"chat_id": chat_id},
        user_label=user_label,
    )

    if result is None:
        await update.message.reply_text("Failed to register. Is the orchestrator running?")
        return

    await update.message.reply_text(f"✅ Telegram notifications registered for {user_label}")


@restricted
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


@restricted
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


def main() -> None:
    application = Application.builder().token(settings.TELEGRAM_API_KEY).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("data", total_data_command))
    application.add_handler(CommandHandler("weather", get_weather))
    application.add_handler(CommandHandler("nikolai_weather", nikolai_weather))
    application.add_handler(CommandHandler("chart", get_chart))
    application.add_handler(CommandHandler("chartdays", get_chart_days))
    application.add_handler(CommandHandler("chartmonth", get_chart_month))
    application.add_handler(CommandHandler("nikolai_power", nikolai_power))
    application.add_handler(CommandHandler("nikolai_powerhistory", nikolai_powerhistory))
    application.add_handler(CommandHandler("nikolai_energytoday", nikolai_energytoday))
    application.add_handler(CommandHandler("nikolai_energyhour", nikolai_energyhour))
    application.add_handler(CommandHandler("nikolai_energydaily", nikolai_energydaily))

    # Reminder commands
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("snooze", snooze_command))
    application.add_handler(CommandHandler("dismiss", dismiss_command))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("registerphone", registerphone_command))
    application.add_handler(CallbackQueryHandler(reminder_callback))

    # Start the outbound Telegram REST API in a background thread
    from src.api.telegram_api import start_api_server
    start_api_server(application.bot)

    application.run_polling(allowed_updates=Update.ALL_TYPES)
