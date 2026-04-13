import datetime
import logging

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.apis.core import HuginCoreClient
from src.config import settings

logger = logging.getLogger(__name__)

core = HuginCoreClient(settings.CORE_API_URL)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Help!")


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


async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    image = core.get_weather_image(settings.YR_ID)
    if image is None:
        await update.message.reply_text("Could not fetch weather.")
        return
    await update.message.reply_photo(image)


async def nikolai_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    image = core.get_weather_image(settings.NIKOLAI_YR_ID)
    if image is None:
        await update.message.reply_text("Could not fetch weather.")
        return
    await update.message.reply_photo(image)


async def get_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    image = core.get_daily_chart()
    if image is None:
        await update.message.reply_text("Could not generate chart.")
        return
    await update.message.reply_photo(image)


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

    application.run_polling(allowed_updates=Update.ALL_TYPES)
