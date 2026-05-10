import re
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser

from src.services.print_service import PrintService

PRINTER_WIDTH = 48


class NewsService:
    def __init__(self):
        self.print_service = PrintService()

    def fetch_and_print(self, feed_url: str, count: int = 5) -> dict:
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            raise Exception(f"Failed to parse feed from {feed_url}: {getattr(feed, 'bozo_exception', 'unknown error')}")

        entries = feed.entries[:count]
        feed_title = feed.feed.get("title", feed_url)

        lines = self._format_entries(entries)
        now = datetime.now(ZoneInfo("Europe/Oslo")).strftime("%d.%m.%Y  %H:%M")

        self.print_service.print_content(
            title=feed_title,
            lines=lines,
            footer=f"Skrevet ut {now}"
        )

        return {
            "feed": feed_title,
            "count": len(entries),
            "headlines": [e.get("title", "") for e in entries]
        }

    def _format_entries(self, entries: list) -> list:
        lines = []
        divider = "-" * PRINTER_WIDTH

        for i, entry in enumerate(entries):
            title = entry.get("title", "(uten tittel)")
            summary = entry.get("summary", entry.get("description", ""))
            summary = self._clean_summary(summary)

            # Uppercase title for emphasis on thermal printer
            lines.append(title.upper()[:PRINTER_WIDTH])

            if summary:
                excerpt_lines = textwrap.wrap(summary[:600], width=PRINTER_WIDTH)[:8]
                lines.extend(excerpt_lines)

            if i < len(entries) - 1:
                lines.append(divider)

        return lines

    @staticmethod
    def _clean_summary(text: str) -> str:
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Remove bare URLs (http/https lines)
        text = re.sub(r"https?://\S+", "", text)
        # Collapse whitespace and punctuation left behind
        text = re.sub(r"[\s,;:]+", " ", text).strip()
        # Discard if nothing meaningful remains (< 20 chars)
        return text if len(text) >= 20 else ""
