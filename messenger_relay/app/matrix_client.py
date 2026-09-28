from __future__ import annotations

import logging
import uuid
from urllib.parse import quote

import httpx

from app.models import RoomInfo

logger = logging.getLogger(__name__)


class MatrixClient:
    def __init__(self, base_url: str, access_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=httpx.Timeout(45, connect=10),
        )

    async def whoami(self) -> str:
        response = await self._client.get("/_matrix/client/v3/account/whoami")
        response.raise_for_status()
        return str(response.json()["user_id"])

    async def sync(self, since: str | None, timeout_ms: int = 30_000) -> dict:
        params: dict[str, str | int] = {"timeout": timeout_ms}
        if since:
            params["since"] = since
        response = await self._client.get("/_matrix/client/v3/sync", params=params)
        response.raise_for_status()
        return response.json()

    async def room_state(self, room_id: str) -> list[dict]:
        encoded_room = quote(room_id, safe="")
        response = await self._client.get(f"/_matrix/client/v3/rooms/{encoded_room}/state")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    async def send_text(self, room_id: str, text: str) -> str:
        encoded_room = quote(room_id, safe="")
        txn_id = uuid.uuid4().hex
        response = await self._client.put(
            f"/_matrix/client/v3/rooms/{encoded_room}/send/m.room.message/{txn_id}",
            json={"msgtype": "m.text", "body": text},
        )
        response.raise_for_status()
        return str(response.json().get("event_id") or txn_id)

    @staticmethod
    def parse_portal(room_id: str, state: list[dict], ghost_prefix: str) -> RoomInfo | None:
        title = ""
        bridge_info: dict | None = None
        members: dict[str, str] = {}
        joined_ghosts = 0
        for event in state:
            event_type = event.get("type")
            content = event.get("content") or {}
            if event_type == "m.room.name":
                title = str(content.get("name") or "")
            elif event_type in {"m.bridge", "uk.half-shot.bridge"}:
                protocol_id = str((content.get("protocol") or {}).get("id") or "").lower()
                if protocol_id in {"facebook", "messenger", "meta"} or protocol_id.startswith("facebook"):
                    bridge_info = content
            elif event_type == "m.room.member" and content.get("membership") == "join":
                user_id = str(event.get("state_key") or "")
                display_name = str(content.get("displayname") or user_id)
                members[user_id] = display_name
                if ghost_prefix and user_id.startswith(ghost_prefix):
                    joined_ghosts += 1

        if bridge_info is None:
            return None
        channel = bridge_info.get("channel") or {}
        thread_id = str(channel.get("id") or "").strip()
        if not thread_id:
            return None
        title = str(channel.get("displayname") or title or thread_id)
        return RoomInfo(
            room_id=room_id,
            thread_id=thread_id,
            title=title,
            chat_type="group" if joined_ghosts > 1 else "private",
            members=members,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
