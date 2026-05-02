import asyncio
import logging

import httpx

from app.config import DestinationConfig
from app.destinations.base import AbstractDestination

logger = logging.getLogger(__name__)


class WebhookAdapter(AbstractDestination):
    def __init__(self, config: DestinationConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._config.headers,
                timeout=self._config.timeout,
            )
        return self._client

    async def send(self, payload: dict) -> None:
        retry = self._config.retry
        last_exc: Exception | None = None

        for attempt in range(1, retry.max_attempts + 1):
            try:
                response = await self._get_client().post(self._config.url, json=payload)
                response.raise_for_status()
                logger.debug(
                    "Webhook '%s' delivered (attempt %d): HTTP %d",
                    self._config.id, attempt, response.status_code,
                )
                return
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "Webhook '%s' attempt %d/%d failed: %s",
                    self._config.id, attempt, retry.max_attempts, exc,
                )
                if attempt < retry.max_attempts:
                    await asyncio.sleep(retry.backoff_seconds * (2 ** (attempt - 1)))

        logger.error(
            "Webhook '%s' delivery failed after %d attempt(s): %s",
            self._config.id, retry.max_attempts, last_exc,
        )

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
