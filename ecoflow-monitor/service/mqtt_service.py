import json
import logging
import ssl
import threading

import paho.mqtt.client as mqtt

from ecoflow_client import EcoflowClient
from service.config import ECOFLOW_ACCESS_KEY, ECOFLOW_SECRET_KEY, ECOFLOW_BASE_URL
from service.database import get_session
from service.models import PowerReading

log = logging.getLogger(__name__)

RECONNECT_DELAY = 30  # seconds between reconnect attempts


class MQTTService:
    def __init__(self):
        self.client_api = EcoflowClient(
            access_key=ECOFLOW_ACCESS_KEY,
            secret_key=ECOFLOW_SECRET_KEY,
            base_url=ECOFLOW_BASE_URL,
        )
        self.device_sn = None
        self.topic_quota = None
        self.topic_status = None
        self.mqttc = None
        self._thread = None
        self._stop_event = threading.Event()
        self._first_message_logged = False
        self._last_values = {"pv1": None, "pv2": None, "grid_power": None, "grid_status": None}

    def _setup(self):
        """Fetch device info and fresh MQTT credentials, create a new client."""
        devices = self.client_api.get_device_list().json()
        self.device_sn = devices["data"][0]["sn"]
        device_name = devices["data"][0]["deviceName"]
        log.info(f"Device: {device_name} ({self.device_sn})")

        cert = self.client_api.get_mqtt_certification().json()["data"]
        log.info(f"MQTT broker: {cert['protocol']}://{cert['url']}:{cert['port']}")

        account = cert["certificateAccount"]
        self.topic_quota = f"/open/{account}/{self.device_sn}/quota"
        self.topic_status = f"/open/{account}/{self.device_sn}/status"

        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc.username_pw_set(account, cert["certificatePassword"])
        self.mqttc.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)

        self.mqttc.on_connect = self._on_connect
        self.mqttc.on_message = self._on_message
        self.mqttc.on_disconnect = self._on_disconnect

        self.mqttc.connect(cert["url"], int(cert["port"]))

    def _on_connect(self, mqttc, userdata, flags, rc, properties=None):
        if rc == 0:
            log.info("Connected to MQTT broker")
            mqttc.subscribe(self.topic_quota)
            mqttc.subscribe(self.topic_status)
            log.info(f"Subscribed to {self.topic_quota} and {self.topic_status}")
            self._first_message_logged = False
        else:
            log.error(f"MQTT connection failed with code {rc}")

    def _on_message(self, mqttc, userdata, msg):
        try:
            try:
                payload = json.loads(msg.payload.decode())
            except json.JSONDecodeError:
                log.warning(f"Non-JSON message on {msg.topic}")
                return

            if msg.topic == self.topic_status:
                status = payload.get("params", {}).get("status", "?")
                log.info(f"Device {'ONLINE' if status == 1 else 'OFFLINE'}")
                return

            # Quota heartbeat
            params = payload.get("param", payload.get("params", payload))

            pv1 = params.get("powGetPv")
            pv2 = params.get("powGetPv2")
            grid_power = params.get("gridConnectionPower")
            grid_status = params.get("gridConnectionSta")

            # Only save if we have at least one power value
            if pv1 is not None or pv2 is not None or grid_power is not None:
                self._save_reading(pv1, pv2, grid_power, grid_status)
                parts = []
                if pv1 is not None:
                    parts.append(f"PV1: {pv1:.1f}W")
                if pv2 is not None:
                    parts.append(f"PV2: {pv2:.1f}W")
                if grid_power is not None:
                    parts.append(f"Grid: {grid_power:.1f}W")
                summary = ' | '.join(parts)
                if not self._first_message_logged:
                    log.info(f"Receiving data — {summary}")
                    self._first_message_logged = True
                else:
                    log.debug(f"[QUOTA] {summary}")
        except Exception:
            log.exception("Unhandled error in _on_message")

    def _on_disconnect(self, mqttc, userdata, rc, properties=None):
        if rc == 0:
            log.info("MQTT disconnected cleanly")
        else:
            log.warning(f"MQTT disconnected unexpectedly (rc={rc})")

    def _run_loop(self):
        """Reconnect loop: on failure, fetch fresh credentials and retry."""
        while not self._stop_event.is_set():
            try:
                self._setup()
                self.mqttc.loop_forever()
            except Exception:
                log.exception("MQTT loop exited with error")
            finally:
                if self.mqttc:
                    try:
                        self.mqttc.disconnect()
                    except Exception:
                        pass

            if self._stop_event.is_set():
                break

            log.info(f"Reconnecting in {RECONNECT_DELAY}s with fresh credentials...")
            self._stop_event.wait(RECONNECT_DELAY)

        log.info("MQTT loop stopped")

    def _save_reading(self, pv1, pv2, grid_power, grid_status):
        # Update in-memory cache with any non-None values
        if pv1 is not None:
            self._last_values["pv1"] = pv1
        if pv2 is not None:
            self._last_values["pv2"] = pv2
        if grid_power is not None:
            self._last_values["grid_power"] = grid_power
        if grid_status is not None:
            self._last_values["grid_status"] = grid_status

        try:
            with get_session() as session:
                reading = PowerReading(
                    pv1_power=pv1 if pv1 is not None else self._last_values["pv1"],
                    pv2_power=pv2 if pv2 is not None else self._last_values["pv2"],
                    grid_power=grid_power if grid_power is not None else self._last_values["grid_power"],
                    grid_status=grid_status if grid_status is not None else self._last_values["grid_status"],
                )
                session.add(reading)
        except Exception:
            log.exception("Failed to save power reading")

    def is_alive(self):
        """Check if the MQTT listener thread is still running."""
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        """Start MQTT listener in a background thread with auto-reconnect."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log.info("MQTT listener started")

    def stop(self):
        self._stop_event.set()
        if self.mqttc:
            self.mqttc.disconnect()
