from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class NomadSite:
    """Small static NomadNet-compatible Micron page server."""

    def __init__(
        self,
        rns,
        identity,
        pages_path: Path,
        name: str,
        announce_interval_seconds: int,
    ) -> None:
        self._rns = rns
        self._pages_path = pages_path.resolve()
        self._name = name
        self._announce_interval = announce_interval_seconds
        self._destination = rns.Destination(
            identity,
            rns.Destination.IN,
            rns.Destination.SINGLE,
            "nomadnetwork",
            "node",
        )
        self._register_pages()
        self._running = True
        self._thread = threading.Thread(target=self._announce_loop, daemon=True)

    @property
    def destination_hash(self) -> str:
        return self._destination.hash.hex()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def announce(self) -> None:
        self._destination.announce(app_data=self._name.encode("utf-8"))

    def _register_pages(self) -> None:
        self._pages_path.mkdir(parents=True, exist_ok=True)
        for page in self._pages_path.rglob("*"):
            if not page.is_file() or page.name.startswith(".") or page.name.endswith(".allowed"):
                continue
            relative = page.relative_to(self._pages_path).as_posix()
            self._destination.register_request_handler(
                f"/page/{relative}",
                response_generator=self._serve_page,
                allow=self._rns.Destination.ALLOW_ALL,
            )

    def _serve_page(self, path, data, request_id, *args):
        relative = str(path).removeprefix("/page/")
        requested = (self._pages_path / relative).resolve()
        if self._pages_path not in requested.parents or not requested.is_file():
            return None
        return requested.read_bytes()

    def _announce_loop(self) -> None:
        # Delay initial announce to allow interfaces to come up.
        time.sleep(6)
        while self._running:
            try:
                self.announce()
            except Exception:
                logger.exception("Could not announce NomadNet site")
            deadline = time.monotonic() + self._announce_interval
            while self._running and time.monotonic() < deadline:
                time.sleep(min(5, max(0, deadline - time.monotonic())))

