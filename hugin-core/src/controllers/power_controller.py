from collections import defaultdict
from datetime import datetime, timedelta

import pytz
from flask import Blueprint, jsonify, request

from src.clients.growatt import GrowattClient
from src.database import get_session
from src.models.power import PowerReading

power_blueprint = Blueprint("power", __name__)

growatt_client = GrowattClient()


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
    data = growatt_client.get_inverter_data()
    if data is None:
        return jsonify({"error": "Could not fetch Growatt data"}), 502
    return jsonify(data)
