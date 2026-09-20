from __future__ import annotations

import html
import os
import re
import xml.etree.ElementTree as ET

import requests

from src.commands.base_command import BaseCommand
from src.models.parsed_command import ParsedCommand


def _headlines(xml: bytes, count: int) -> list[str]:
    root = ET.fromstring(xml)
    titles: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() == "title" and element.text:
            title = re.sub(r"\s+", " ", html.unescape(element.text)).strip()
            if title and title not in titles:
                titles.append(title)
    # The first RSS/Atom title is normally the feed title.
    return titles[1:count + 1] if len(titles) > 1 else titles[:count]


class NewsCommand(BaseCommand):
    path = "news"
    aliases = ["headlines"]
    description = "Show a few headlines from your configured RSS feed"
    usage = "news [count]"

    def execute(self, cmd: ParsedCommand) -> str:
        count = 3
        if cmd.positional and cmd.positional[0].isdigit():
            count = max(1, min(int(cmd.positional[0]), 10))
        feed_url = cmd.user_config.get("news_feed_url") or os.environ.get("NEWS_FEED_URL", "")
        if not feed_url:
            return "No news feed configured. Set config.news_feed_url."
        try:
            response = requests.get(feed_url, timeout=(5, 15), headers={"User-Agent": "hugin-sms/1.0"})
            response.raise_for_status()
            titles = _headlines(response.content, count)
        except Exception:
            return "News unavailable"
        if not titles:
            return "No headlines found"
        return "News: " + " | ".join(f"{i}. {title}" for i, title in enumerate(titles, 1))
