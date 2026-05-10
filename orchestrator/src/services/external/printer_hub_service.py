import json

from src.persistence.DatabaseLogger import DatabaseLogger
from src.api.printer_hub.print_job import send_print_news
from src.api.printer_hub.print_weather import send_print_weather


def run_print_news(param: str = ""):
    logger = DatabaseLogger()

    if not param:
        raise Exception("Missing parameter JSON (feed_url required)")

    params = json.loads(param)
    feed_url = params.get("feed_url")
    if not feed_url:
        raise Exception("feed_url is required in parameter JSON")

    count = int(params.get("count", 5))

    logger.log_info(f"Fetching and printing headlines from {feed_url} (count={count})")
    result = send_print_news(feed_url=feed_url, count=count)
    logger.log_info(f"Printed {result.get('count', '?')} headlines from '{result.get('feed', feed_url)}'")
    logger.log_info(f"Headlines: {', '.join(result.get('headlines', []))}")


def run_print_weather(param: str = ""):
    logger = DatabaseLogger()

    yr_id = param.strip() or None
    logger.log_info(f"Printing weather meteogram (yr_id={yr_id or 'from env'}")
    result = send_print_weather(yr_id=yr_id)
    logger.log_info(f"Weather print done: {result}")