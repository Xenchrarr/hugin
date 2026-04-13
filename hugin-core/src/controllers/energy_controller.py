import traceback
from datetime import datetime, timedelta

import pytz
from flask import Blueprint, jsonify, request
from sqlalchemy import desc

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.config import settings
from src.database import get_session
from src.models.power import PowerReading, DailyEnergy
from src.services.aggregator import run_aggregation
from src.services.log_service import log_info, log_error

energy_blueprint = Blueprint("energy", __name__)


@energy_blueprint.route("/today")
def today_energy():
    tz = pytz.timezone(settings.TIMEZONE)
    today = datetime.now(tz).date()
    day_start = tz.localize(datetime.combine(today, datetime.min.time()))

    with get_session() as session:
        readings = (
            session.query(PowerReading)
            .filter(PowerReading.recorded_at >= day_start)
            .order_by(PowerReading.recorded_at.asc())
            .all()
        )

        if len(readings) < 2:
            return jsonify({"date": str(today), "total_energy_wh": 0, "reading_count": len(readings)})

        pv1_energy = 0.0
        pv2_energy = 0.0
        grid_energy = 0.0

        for i in range(1, len(readings)):
            prev = readings[i - 1]
            curr = readings[i]
            dt_hours = (curr.recorded_at - prev.recorded_at).total_seconds() / 3600.0
            max_gap = 90.0 / 60.0 if (prev.grid_power or 0) >= 70 else 10.0 / 60.0
            if dt_hours > max_gap:
                continue
            pv1_energy += ((prev.pv1_power or 0) + (curr.pv1_power or 0)) / 2.0 * dt_hours
            pv2_energy += ((prev.pv2_power or 0) + (curr.pv2_power or 0)) / 2.0 * dt_hours
            grid_energy += ((prev.grid_power or 0) + (curr.grid_power or 0)) / 2.0 * dt_hours

        return jsonify({
            "date": str(today),
            "pv1_energy_wh": round(pv1_energy, 1),
            "pv2_energy_wh": round(pv2_energy, 1),
            "total_energy_wh": round(pv1_energy + pv2_energy, 1),
            "grid_energy_wh": round(grid_energy, 1),
            "reading_count": len(readings),
        })


@energy_blueprint.route("/hour")
def hour_energy():
    since = datetime.now(pytz.UTC) - timedelta(hours=1)

    with get_session() as session:
        readings = (
            session.query(PowerReading)
            .filter(PowerReading.recorded_at >= since)
            .order_by(PowerReading.recorded_at.asc())
            .all()
        )

        if len(readings) < 2:
            return jsonify({"period": "last_hour", "total_energy_wh": 0, "reading_count": len(readings)})

        pv1_energy = 0.0
        pv2_energy = 0.0
        grid_energy = 0.0

        for i in range(1, len(readings)):
            prev = readings[i - 1]
            curr = readings[i]
            dt_hours = (curr.recorded_at - prev.recorded_at).total_seconds() / 3600.0
            max_gap = 90.0 / 60.0 if (prev.grid_power or 0) >= 70 else 10.0 / 60.0
            if dt_hours > max_gap:
                continue
            pv1_energy += ((prev.pv1_power or 0) + (curr.pv1_power or 0)) / 2.0 * dt_hours
            pv2_energy += ((prev.pv2_power or 0) + (curr.pv2_power or 0)) / 2.0 * dt_hours
            grid_energy += ((prev.grid_power or 0) + (curr.grid_power or 0)) / 2.0 * dt_hours

        return jsonify({
            "period": "last_hour",
            "pv1_energy_wh": round(pv1_energy, 1),
            "pv2_energy_wh": round(pv2_energy, 1),
            "total_energy_wh": round(pv1_energy + pv2_energy, 1),
            "grid_energy_wh": round(grid_energy, 1),
            "reading_count": len(readings),
        })


@energy_blueprint.route("/daily")
def daily_energy():
    days = request.args.get("days", 30, type=int)
    days = max(1, min(days, 365))

    with get_session() as session:
        records = (
            session.query(DailyEnergy)
            .order_by(desc(DailyEnergy.date))
            .limit(days)
            .all()
        )
        return jsonify({
            "count": len(records),
            "days": [
                {
                    "date": str(r.date),
                    "pv1_energy_wh": round(r.pv1_energy_wh, 1),
                    "pv2_energy_wh": round(r.pv2_energy_wh, 1),
                    "total_energy_wh": round(r.total_energy_wh, 1),
                    "grid_energy_wh": round(r.grid_energy_wh, 1),
                    "pv1_max_power": round(r.pv1_max_power, 1),
                    "pv2_max_power": round(r.pv2_max_power, 1),
                    "grid_max_power": round(r.grid_max_power, 1),
                    "reading_count": r.reading_count,
                }
                for r in records
            ],
        })


@energy_blueprint.route("/aggregation/run", methods=["POST"])
def trigger_aggregation():
    try:
        body = request.get_json(silent=True) or {}
        job_run_id = body.get('job_run_id')

        if job_run_id:
            thread_local = ThreadLocalSingleton.instance().thread_local
            thread_local.job_run_id = job_run_id
            log_info(f"Starting aggregation with job_run_id: {job_run_id}")

        run_aggregation()

        if job_run_id:
            log_info("Aggregation completed successfully")

        return jsonify({"ok": True, "message": "Aggregation completed"})
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        if job_run_id:
            log_error(f"Aggregation failed: {e}", stack_trace=stack_trace)
        return jsonify({"ok": False, "message": f"Aggregation failed: {e}"}), 500
