import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.persistence.DatabaseLogger import DatabaseLogger
from src.api.printer_hub.print_job import send_print_content
from src.api.printer_hub.print_weather import send_print_weather
from src.api.printer_hub.print_today import send_print_today


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

    now = datetime.now(ZoneInfo("Europe/Oslo")).strftime("%d.%m.%Y  %H:%M")
    send_print_content(lines=lines, title=feed_title, footer=f"Skrevet ut {now}")

    logger.log_info(f"Printed {len(headlines)} headlines from '{feed_title}'")
    logger.log_info(f"Headlines: {', '.join(headlines)}")


def run_print_weather(param: str = ""):
    logger = DatabaseLogger()

    yr_id = param.strip() or None
    logger.log_info(f"Printing weather meteogram (yr_id={yr_id or 'from env'}")
    result = send_print_weather(yr_id=yr_id)
    logger.log_info(f"Weather print done: {result}")


def run_print_today(param: str = ""):
    logger = DatabaseLogger()

    logger.log_info("Printing today view (calendar + reminders)")
    result = send_print_today()
    logger.log_info(
        f"Today print done: {result.get('event_count', '?')} event(s), "
        f"{result.get('reminder_count', '?')} reminder(s)"
    )