from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class Config:
    data_path: Path
    rns_config_path: Path
    identity_path: Path
    lxmf_storage_path: Path
    state_path: Path
    pages_path: Path
    orchestrator_url: str
    service_key: str
    endpoint_key: str
    display_name: str
    node_name: str
    api_port: int
    announce_interval_seconds: int
    config_refresh_seconds: int
    path_timeout_seconds: int
    enable_transport: bool
    share_instance: bool
    panic_on_interface_error: bool
    enable_rnode: bool
    rnode_port: str
    rnode_frequency: int
    rnode_bandwidth: int
    rnode_txpower: int
    rnode_spreading_factor: int
    rnode_coding_rate: int
    enable_tcp_server: bool
    tcp_listen_ip: str
    tcp_listen_port: int
    propagation_enabled: bool
    outbound_propagation_node: str
    message_storage_megabytes: int
    inbound_stamp_cost: int | None

    @classmethod
    def from_env(cls) -> "Config":
        data_path = Path(os.environ.get("RETICULUM_DATA_PATH", "/data"))
        stamp_cost = _int("RETICULUM_INBOUND_STAMP_COST", 0)
        return cls(
            data_path=data_path,
            rns_config_path=data_path / "rns",
            identity_path=data_path / "identity",
            lxmf_storage_path=data_path / "lxmf",
            state_path=data_path / "state" / "relay.json",
            pages_path=Path(os.environ.get("RETICULUM_PAGES_PATH", str(data_path / "pages"))),
            orchestrator_url=os.environ.get(
                "ORCHESTRATOR_API_URL", "http://orchestrator:6000"
            ).rstrip("/"),
            service_key=os.environ.get("SERVICE_KEY", ""),
            endpoint_key=os.environ.get("MESSAGE_RELAY_ENDPOINT_KEY", "reticulum-main"),
            display_name=os.environ.get("RETICULUM_DISPLAY_NAME", "Hugin"),
            node_name=os.environ.get("RETICULUM_NODE_NAME", "Hugin Node"),
            api_port=_int("RETICULUM_API_PORT", 8082),
            announce_interval_seconds=_int("RETICULUM_ANNOUNCE_INTERVAL_SECONDS", 21600),
            config_refresh_seconds=_int("RETICULUM_CONFIG_REFRESH_SECONDS", 30),
            path_timeout_seconds=_int("RETICULUM_PATH_TIMEOUT_SECONDS", 15),
            enable_transport=_bool("RETICULUM_ENABLE_TRANSPORT", True),
            share_instance=_bool("RETICULUM_SHARE_INSTANCE", True),
            panic_on_interface_error=_bool("RETICULUM_PANIC_ON_INTERFACE_ERROR", False),
            enable_rnode=_bool("RETICULUM_RNODE_ENABLED", True),
            rnode_port=os.environ.get("RETICULUM_RNODE_PORT", "/dev/ttyACM0"),
            rnode_frequency=_int("RETICULUM_RNODE_FREQUENCY", 868000000),
            rnode_bandwidth=_int("RETICULUM_RNODE_BANDWIDTH", 125000),
            rnode_txpower=_int("RETICULUM_RNODE_TXPOWER", 14),
            rnode_spreading_factor=_int("RETICULUM_RNODE_SPREADING_FACTOR", 7),
            rnode_coding_rate=_int("RETICULUM_RNODE_CODING_RATE", 5),
            enable_tcp_server=_bool("RETICULUM_TCP_SERVER_ENABLED", True),
            tcp_listen_ip=os.environ.get("RETICULUM_TCP_LISTEN_IP", "0.0.0.0"),
            tcp_listen_port=_int("RETICULUM_TCP_LISTEN_PORT", 4242),
            propagation_enabled=_bool("RETICULUM_PROPAGATION_ENABLED", True),
            outbound_propagation_node=os.environ.get(
                "RETICULUM_OUTBOUND_PROPAGATION_NODE", ""
            ).strip().lower(),
            message_storage_megabytes=_int("RETICULUM_MESSAGE_STORAGE_MB", 512),
            inbound_stamp_cost=stamp_cost if stamp_cost > 0 else None,
        )

    def ensure_directories(self) -> None:
        for path in (
            self.data_path,
            self.rns_config_path,
            self.lxmf_storage_path,
            self.state_path.parent,
            self.pages_path,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def write_rns_config(self) -> Path:
        """Render the authoritative RNS config from Hugin environment settings."""
        self.ensure_directories()
        lines = [
            "[reticulum]",
            f"  enable_transport = {'Yes' if self.enable_transport else 'No'}",
            f"  share_instance = {'Yes' if self.share_instance else 'No'}",
            (
                "  panic_on_interface_error = "
                f"{'Yes' if self.panic_on_interface_error else 'No'}"
            ),
            "",
            "[logging]",
            "  loglevel = 4",
            "",
            "[interfaces]",
        ]
        if self.enable_rnode:
            lines.extend(
                [
                    "  [[RNode LoRa]]",
                    "    type = RNodeInterface",
                    "    enabled = Yes",
                    f"    port = {self.rnode_port}",
                    f"    frequency = {self.rnode_frequency}",
                    f"    bandwidth = {self.rnode_bandwidth}",
                    f"    txpower = {self.rnode_txpower}",
                    f"    spreadingfactor = {self.rnode_spreading_factor}",
                    f"    codingrate = {self.rnode_coding_rate}",
                    "",
                ]
            )
        if self.enable_tcp_server:
            lines.extend(
                [
                    "  [[TCP Server]]",
                    "    type = TCPServerInterface",
                    "    enabled = Yes",
                    f"    listen_ip = {self.tcp_listen_ip}",
                    f"    listen_port = {self.tcp_listen_port}",
                    "",
                ]
            )
        path = self.rns_config_path / "config"
        temporary = path.with_suffix(".tmp")
        temporary.write_text("\n".join(lines), encoding="utf-8")
        temporary.replace(path)
        return path
