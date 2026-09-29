from __future__ import annotations

import logging
from typing import Any, Callable

from app.chat import ChatStore


logger = logging.getLogger(__name__)


class AnnounceHandler:
    """Capture live Reticulum announces without including path responses."""

    aspect_filter = None
    receive_path_responses = False

    def __init__(
        self,
        rns: Any,
        lxmf: Any,
        store: ChatStore,
        peer_name_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self._rns = rns
        self._lxmf = lxmf
        self._store = store
        self._peer_name_callback = peer_name_callback

    def received_announce(
        self,
        destination_hash: bytes,
        announced_identity: Any,
        app_data: bytes | None,
        announce_packet_hash: bytes | None = None,
        is_path_response: bool = False,
    ) -> None:
        try:
            aspect = self._aspect(destination_hash, announced_identity)
            display_name = self._display_name(aspect, app_data)
            hops = self._rns.Transport.hops_to(destination_hash)
            destination_hex = destination_hash.hex()
            self._store.record_announce(
                destination_hex,
                self._hex(getattr(announced_identity, "hash", None)) or None,
                aspect,
                display_name,
                self._plain_text(app_data),
                int(hops) if isinstance(hops, int) and hops >= 0 else None,
                self._hex(announce_packet_hash) or None,
                bool(is_path_response),
            )
            if aspect == "lxmf.delivery" and display_name and self._peer_name_callback:
                self._peer_name_callback(destination_hex, display_name)
        except Exception:
            logger.exception("Could not record Reticulum announce")

    def _aspect(self, destination_hash: bytes, identity: Any) -> str:
        known = (
            ("lxmf.delivery", "lxmf", "delivery"),
            ("lxmf.propagation", "lxmf", "propagation"),
            ("nomadnetwork.node", "nomadnetwork", "node"),
        )
        for label, app_name, aspect in known:
            try:
                if self._rns.Destination.hash(identity, app_name, aspect) == destination_hash:
                    return label
            except Exception:
                continue
        return "unknown"

    def _display_name(self, aspect: str, app_data: bytes | None) -> str | None:
        if not app_data:
            return None
        try:
            if aspect == "lxmf.delivery":
                return self._clean(self._lxmf.display_name_from_app_data(app_data))
            if aspect == "lxmf.propagation":
                return self._clean(self._lxmf.pn_name_from_app_data(app_data))
            if aspect == "nomadnetwork.node":
                return self._clean(app_data.decode("utf-8"))
        except Exception:
            return None
        return None

    @staticmethod
    def _plain_text(app_data: bytes | None) -> str | None:
        if not app_data:
            return None
        try:
            value = app_data.decode("utf-8").strip()
            if value and value.isprintable():
                return value[:256]
        except (UnicodeDecodeError, AttributeError):
            pass
        return None

    @staticmethod
    def _clean(value: Any) -> str | None:
        if value is None:
            return None
        result = str(value).strip()
        return result[:256] if result else None

    @staticmethod
    def _hex(value: Any) -> str:
        return value.hex() if isinstance(value, bytes) else str(value or "")
