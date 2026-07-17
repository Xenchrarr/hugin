import logging
from collections import defaultdict
from datetime import datetime, timedelta

import pytz
import requests
from flask import Blueprint, jsonify, request

from src.clients.deye import DeyeClient
from src.clients.growatt import GrowattClient
from src.config import settings
from src.database import get_session
from src.models.power import PowerReading
from src.services.user_config_service import get_primary_user_config, get_user_config

log = logging.getLogger(__name__)

power_blueprint = Blueprint("power", __name__)


@power_blueprint.route("/current")
def current_power():
    with get_session() as session:
        reading = (
            session.query(PowerReading)
            .order_by(PowerReading.recorded_at.desc())
            .first()
        )
        if not reading:
            return jsonify({"error": "No readings yet"}), 404
        return jsonify({
            "recorded_at": reading.recorded_at.isoformat(),
            "pv1_power": reading.pv1_power,
            "pv2_power": reading.pv2_power,
            "grid_power": reading.grid_power,
            "grid_status": reading.grid_status,
        })


@power_blueprint.route("/history")
def power_history():
    hours = request.args.get("hours", 1, type=float)
    hours = max(0.1, min(hours, 168))
    since = datetime.now(pytz.UTC) - timedelta(hours=hours)

    with get_session() as session:
        readings = (
            session.query(PowerReading)
            .filter(PowerReading.recorded_at >= since)
            .order_by(PowerReading.recorded_at.asc())
            .all()
        )

        buckets: dict[datetime, list] = defaultdict(list)
        for r in readings:
            ts = r.recorded_at
            bucket_ts = ts.replace(minute=(ts.minute // 10) * 10, second=0, microsecond=0)
            buckets[bucket_ts].append(r)

        result = []
        for bucket_ts in sorted(buckets):
            group = buckets[bucket_ts]
            n = len(group)
            avg_pv1 = round(sum(r.pv1_power or 0 for r in group) / n, 1)
            avg_pv2 = round(sum(r.pv2_power or 0 for r in group) / n, 1)
            avg_grid = round(sum(r.grid_power or 0 for r in group) / n, 1)
            status_counts: dict[str, int] = defaultdict(int)
            for r in group:
                status_counts[r.grid_status] += 1
            grid_status = max(status_counts, key=status_counts.get)
            result.append({
                "recorded_at": bucket_ts.isoformat(),
                "pv1_power": avg_pv1,
                "pv2_power": avg_pv2,
                "grid_power": avg_grid,
                "grid_status": grid_status,
                "reading_count": n,
            })

        return jsonify({
            "count": len(result),
            "since": since.isoformat(),
            "interval_minutes": 10,
            "readings": result,
        })


@power_blueprint.route("/growatt")
def growatt_data():
    try:
        config = get_primary_user_config()
    except RuntimeError as e:
        return jsonify({"error": f"Could not fetch user config: {e}"}), 503

    username = config.get("growatt_username", "")
    password = config.get("growatt_password", "")
    if not username or not password:
        return jsonify({"error": "Growatt credentials not configured in user settings"}), 503

    data = GrowattClient(username, password).get_inverter_data()
    if data is None:
        return jsonify({"error": "Could not fetch Growatt data"}), 502
    return jsonify(data)


DEYE_USER_ID = 4


@power_blueprint.route("/deye")
def deye_data():
    try:
        config = get_user_config(DEYE_USER_ID)
    except RuntimeError as e:
        log.error("deye_data: could not fetch user config: %s", e)
        return jsonify({"error": f"Could not fetch user config: {e}"}), 503

    app_id = config.get("deye_app_id", "")
    app_secret = config.get("deye_app_secret", "")
    email = config.get("deye_email", "")
    password = config.get("deye_password", "")
    device_sn = config.get("deye_device_sn", "")
    missing = [k for k, v in {"deye_app_id": app_id, "deye_app_secret": app_secret, "deye_email": email, "deye_password": password, "deye_device_sn": device_sn}.items() if not v]
    if missing:
        log.error("deye_data: missing credentials: %s", missing)
        return jsonify({"error": "Deye credentials not configured in user settings"}), 503

    data = DeyeClient(app_id, app_secret, email, password, device_sn).get_inverter_data()
    if data is None:
        return jsonify({"error": "Could not fetch Deye data"}), 502
    return jsonify(data)


@power_blueprint.route("/deye/webhook", methods=["POST"])
def deye_webhook():
    """Receive a normalized Telegram message from telegram_relay, fetch Deye data,
    and push the result back to the originating Telegram chat."""
    body = request.get_json(silent=True) or {}
    chat_id = body.get("chat_id")
    if not chat_id:
        return jsonify({"error": "chat_id missing"}), 400

    try:
        config = get_user_config(DEYE_USER_ID)
    except RuntimeError as e:
        log.error("deye_webhook: could not fetch user config: %s", e)
        return jsonify({"error": str(e)}), 503

    app_id = config.get("deye_app_id", "")
    app_secret = config.get("deye_app_secret", "")
    email = config.get("deye_email", "")
    password = config.get("deye_password", "")
    device_sn = config.get("deye_device_sn", "")
    if not all([app_id, app_secret, email, password, device_sn]):
        log.warning("deye_webhook: Deye credentials not configured")
        return jsonify({"error": "Deye credentials not configured"}), 503

    data = DeyeClient(app_id, app_secret, email, password, device_sn).get_inverter_data()
    if data is None:
        log.error("deye_webhook: failed to fetch inverter data")
        return jsonify({"error": "Could not fetch Deye data"}), 502

    battery = data.get("battery", {})
    soc = battery.get("soc", "N/A")
    power = battery.get("power", "N/A")
    voltage = battery.get("voltage", "N/A")
    status = battery.get("status", "N/A")
    charged = battery.get("dailyChargeEnergy", "N/A")
    discharged = battery.get("dailyDischargeEnergy", "N/A")

    message = (
        f"Solar data\n"
        f"Power now: {data.get('currentPower', 'N/A')}\n"
        f"Today: {data.get('todayEnergy', 'N/A')} kWh\n"
        f"Total: {data.get('totalEnergy', 'N/A')} kWh\n"
        f"This month: {data.get('monthlyEnergy', 'N/A')} kWh\n"
        f"\n"
        f"Battery\n"
        f"State of charge: {soc}%\n"
        f"Power: {power} W\n"
        f"Voltage: {voltage} V\n"
        f"Status: {status}\n"
        f"Charged today: {charged} kWh\n"
        f"Discharged today: {discharged} kWh"
    )

    try:
        resp = requests.post(
            f"{settings.TELEGRAM_BOT_URL}/api/telegram/send",
            json={"chat_id": chat_id, "message": message},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        log.error("deye_webhook: failed to send Telegram message: %s", e)
        return jsonify({"error": "Failed to deliver Telegram message"}), 502

    return jsonify({"ok": True})
