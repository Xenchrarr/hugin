from collections import defaultdict
from datetime import datetime, timedelta

import pytz
from flask import Blueprint, jsonify, request

from src.clients.deye import DeyeClient
from src.clients.growatt import GrowattClient
from src.database import get_session
from src.models.power import PowerReading
from src.services.user_config_service import get_primary_user_config

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


@power_blueprint.route("/deye")
def deye_data():
    try:
        config = get_primary_user_config()
    except RuntimeError as e:
        return jsonify({"error": f"Could not fetch user config: {e}"}), 503

    app_id = config.get("deye_app_id", "")
    app_secret = config.get("deye_app_secret", "")
    email = config.get("deye_email", "")
    password = config.get("deye_password", "")
    device_sn = config.get("deye_device_sn", "")
    if not all([app_id, app_secret, email, password, device_sn]):
        return jsonify({"error": "Deye credentials not configured in user settings"}), 503

    data = DeyeClient(app_id, app_secret, email, password, device_sn).get_inverter_data()
    if data is None:
        return jsonify({"error": "Could not fetch Deye data"}), 502
    return jsonify(data)
