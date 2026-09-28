from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    matrix_url: str
    matrix_access_token: str
    matrix_user_id: str
    matrix_bridge_bot_user_id: str
    matrix_ghost_prefix: str
    orchestrator_url: str
    service_key: str
    source_endpoint_key: str
    state_path: str
    config_refresh_seconds: int


def load_config() -> Config:
    required = {
        "MATRIX_ACCESS_TOKEN": os.environ.get("MATRIX_ACCESS_TOKEN", "").strip(),
        "MATRIX_USER_ID": os.environ.get("MATRIX_USER_ID", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing)}")

    return Config(
        matrix_url=os.environ.get("MATRIX_HOMESERVER_URL", "http://matrix-synapse:8008").rstrip("/"),
        matrix_access_token=required["MATRIX_ACCESS_TOKEN"],
        matrix_user_id=required["MATRIX_USER_ID"],
        matrix_bridge_bot_user_id=os.environ.get(
            "MATRIX_BRIDGE_BOT_USER_ID", "@facebookbot:hugin.local"
        ).strip(),
        matrix_ghost_prefix=os.environ.get("MATRIX_GHOST_PREFIX", "@facebook_").strip(),
        orchestrator_url=os.environ.get(
            "ORCHESTRATOR_API_URL", "http://orchestrator:6000"
        ).rstrip("/"),
        service_key=os.environ.get("SERVICE_KEY", ""),
        source_endpoint_key=os.environ.get(
            "MESSAGE_RELAY_ENDPOINT_KEY", "messenger-main"
        ).strip(),
        state_path=os.environ.get("MESSENGER_RELAY_STATE_PATH", "/data/state.sqlite3"),
        config_refresh_seconds=max(
            5, int(os.environ.get("MESSENGER_CONFIG_REFRESH_SECONDS", "30"))
        ),
    )
