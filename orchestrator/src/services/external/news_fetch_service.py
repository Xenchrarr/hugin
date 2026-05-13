import logging
import re
import textwrap

import feedparser
import trafilatura

from src.persistence.DatabaseLogger import DatabaseLogger

log = logging.getLogger(__name__)

PRINTER_WIDTH = 48


class NewsFetchService:
    def __init__(self, summarize: bool = False):
        self._llm = None
        if summarize:
            try:
                from src.services.external.llm_service import LLMService
                self._llm = LLMService()
            except Exception as e:
                log.warning("LLM service unavailable, falling back to RSS excerpts: %s", e)

    def fetch_and_format(self, feed_url: str, count: int = 5) -> tuple:
        """Returns (feed_title, lines, headlines)."""
        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            raise Exception(
                f"Failed to parse feed from {feed_url}: "
                f"{getattr(feed, 'bozo_exception', 'unknown error')}"
            )

        entries = feed.entries[:count]
        feed_title = feed.feed.get("title", feed_url)
        headlines = [e.get("title", "") for e in entries]
        lines = self._format_entries(entries)

        return feed_title, lines, headlines

    def _format_entries(self, entries: list) -> list:
        lines = []
        divider = "-" * PRINTER_WIDTH

        for i, entry in enumerate(entries):
            title = entry.get("title", "(uten tittel)")
            DatabaseLogger().log_info(f"Processing article: {title}")
            summary = self._get_summary(entry)

            lines.extend(textwrap.wrap(title.upper(), PRINTER_WIDTH))

            if summary:
                lines.extend(textwrap.wrap(summary, width=PRINTER_WIDTH))

            if i < len(entries) - 1:
                lines.append(divider)

        return lines

    def _get_summary(self, entry: dict) -> str:
        link = entry.get("link", "")
        rss_text = entry.get("summary", entry.get("description", ""))
        rss_fallback = self._clean_summary(rss_text)

        if self._llm and link:
            try:
                downloaded = trafilatura.fetch_url(link)
                article_text = trafilatura.extract(downloaded) if downloaded else None
                if article_text:
                    result = self._llm.summarize(article_text)
                    if result:
                        return result
            except Exception as e:
                log.warning("Article fetch/summarize failed for %s: %s", link, e)
                DatabaseLogger().log_warning(f"Article fetch/summarize failed for {link}: {e}")

        return rss_fallback

    @staticmethod
    def _clean_summary(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[\s,;:]+", " ", text).strip()
        return text if len(text) >= 20 else ""
