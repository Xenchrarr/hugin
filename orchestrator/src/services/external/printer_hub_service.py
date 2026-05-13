import json
import os
import textwrap
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.persistence.DatabaseLogger import DatabaseLogger
from src.api.printer_hub.print_job import send_print_content
from src.api.printer_hub.print_image import send_print_image
from src.api.hugin_core.today import get_today
from src.api.hugin_core.shopping import get_shopping_list
from src.api.hugin_core.weather import get_weather_image

_TZ = ZoneInfo("Europe/Oslo")
PRINTER_WIDTH = 48
_YR_ID = os.environ.get("YR_ID", "")


def run_print_news(param: str = ""):
    logger = DatabaseLogger()

    if not param:
        raise Exception("Missing parameter JSON (feed_url required)")

    params = json.loads(param)
    feed_url = params.get("feed_url")
    if not feed_url:
        raise Exception("feed_url is required in parameter JSON")

    count = int(params.get("count", 5))
    summarize = bool(params.get("summarize", False))

    logger.log_info(f"Fetching headlines from {feed_url} (count={count}, summarize={summarize})")

    from src.services.external.news_fetch_service import NewsFetchService
    feed_title, lines, headlines = NewsFetchService(summarize=summarize).fetch_and_format(feed_url, count)

    now = datetime.now(_TZ).strftime("%d.%m.%Y  %H:%M")
    send_print_content(lines=lines, title=feed_title, footer=f"Skrevet ut {now}")

    logger.log_info(f"Printed {len(headlines)} headlines from '{feed_title}'")
    logger.log_info(f"Headlines: {', '.join(headlines)}")


def run_print_weather(param: str = ""):
    logger = DatabaseLogger()

    yr_id = param.strip() or _YR_ID
    if not yr_id:
        raise Exception("No yr_id provided and YR_ID env var is not set")

    logger.log_info(f"Fetching weather image from hugin-core (yr_id={yr_id})")
    image_bytes = get_weather_image(yr_id)

    logger.log_info(f"Printing weather image ({len(image_bytes)} bytes)")
    result = send_print_image(image_bytes)
    logger.log_info(f"Weather print done: {result}")


def run_print_today(param: str = ""):
    logger = DatabaseLogger()

    logger.log_info("Fetching today data from hugin-core")
    data = get_today()

    day_name = data.get("day_name", "").capitalize()
    today_str = data.get("date", "")
    month_name = data.get("month_name", "")

    try:
        day_num = str(datetime.fromisoformat(today_str).day)
    except (ValueError, TypeError):
        day_num = today_str

    title = f"I DAG -- {day_name} {day_num}. {month_name}"
    lines = _format_today(data)
    now = datetime.now(_TZ).strftime("%H:%M")

    send_print_content(lines=lines, title=title, footer=f"Skrevet ut {now}")

    logger.log_info(
        f"Today print done: {len(data.get('events', []))} event(s), "
        f"{len(data.get('reminders', []))} reminder(s)"
    )


def run_print_shopping(param: str = ""):
    logger = DatabaseLogger()

    logger.log_info("Fetching shopping list from hugin-core")
    items = get_shopping_list()

    if not items:
        raise Exception("Shopping list is empty")

    logger.log_info(f"Printing {len(items)} shopping items")
    send_print_content(lines=items, title="Handleliste")
    logger.log_info("Shopping list printed")


def _format_today(data: dict) -> list[str]:
    lines = []
    divider = "-" * PRINTER_WIDTH
    events = data.get("events", [])
    reminders = data.get("reminders", [])

    lines.append("KALENDER")
    lines.append(divider)

    if not events:
        lines.append("  (ingen avtaler i dag)")
    else:
        for event in events:
            summary = event.get("summary", "(uten tittel)")
            cal = event.get("calendar_name", "")
            if event.get("all_day"):
                label = f"* {summary}"
            else:
                time_part = _format_time(event.get("start", ""))
                label = f"{time_part}  {summary}" if time_part else summary
            if cal:
                label = f"{label} ({cal})"
            for wrapped in textwrap.wrap(label, width=PRINTER_WIDTH):
                lines.append(wrapped)

    if reminders:
        lines.append("")
        lines.append("PAMINNELSER")
        lines.append(divider)
        for r in reminders:
            r_title = r.get("title", "(uten tittel)")
            time_part = _format_time(r.get("due_at", ""))
            label = f"{time_part}  {r_title}" if time_part else r_title
            for wrapped in textwrap.wrap(label, width=PRINTER_WIDTH):
                lines.append(wrapped)
            msg = r.get("message") or ""
            if msg:
                for wrapped in textwrap.wrap(f"  {msg}", width=PRINTER_WIDTH)[:3]:
                    lines.append(wrapped)

    return lines


def _format_time(dt_str: str) -> str:
    if not dt_str or "T" not in dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_TZ).strftime("%H:%M")
    except (ValueError, TypeError):
        return ""