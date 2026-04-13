import asyncio
import logging

import aiohttp
import tibber

from src.config import settings

logger = logging.getLogger(__name__)


class TibberClient:
    def __init__(self) -> None:
        self._access_token = settings.TIBBER_ACCESS_TOKEN

    async def subscribe_realtime(self, callback) -> None:
        async with aiohttp.ClientSession() as session:
            connection = tibber.Tibber(
                access_token=self._access_token,
                websession=session,
                user_agent="macbot",
            )
            await connection.update_info()

        home = connection.get_homes()[0]
        await home.rt_subscribe(callback)

        while True:
            await asyncio.sleep(10)
