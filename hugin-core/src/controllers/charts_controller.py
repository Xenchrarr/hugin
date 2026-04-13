import datetime
from collections import defaultdict
from datetime import timedelta

import pytz
from flask import Blueprint, Response, jsonify, request
from sqlalchemy import desc

from src.clients.growatt import GrowattClient
from src.database import get_session
from src.models.power import PowerReading, DailyEnergy
from src.services.chart_service import ChartService

charts_blueprint = Blueprint("charts", __name__)

growatt_client = GrowattClient()
chart_service = ChartService(growatt_client)


def _png_response(image_buf):
    return Response(image_buf.getvalue(), mimetype="image/png")


def _get_power_history_data(hours: float) -> dict | None:
    since = datetime.datetime.now(pytz.UTC) - timedelta(hours=hours)
    with get_session() as session:
        readings = (
            session.query(PowerReading)
            .filter(PowerReading.recorded_at >= since)
            .order_by(PowerReading.recorded_at.asc())
            .all()
        )
        buckets: dict[datetime.datetime, list] = defaultdict(list)
        for r in readings:
            ts = r.recorded_at
            bucket_ts = ts.replace(minute=(ts.minute // 10) * 10, second=0, microsecond=0)
            buckets[bucket_ts].append(r)

        result = []
        for bucket_ts in sorted(buckets):
            group = buckets[bucket_ts]
            n = len(group)
            result.append({
                "recorded_at": bucket_ts.isoformat(),
                "pv1_power": round(sum(r.pv1_power or 0 for r in group) / n, 1),
                "pv2_power": round(sum(r.pv2_power or 0 for r in group) / n, 1),
                "grid_power": round(sum(r.grid_power or 0 for r in group) / n, 1),
            })
        return {"readings": result} if result else None


def _get_daily_energy_data(days: int) -> dict | None:
    with get_session() as session:
        records = (
            session.query(DailyEnergy)
            .order_by(desc(DailyEnergy.date))
            .limit(days)
            .all()
        )
        if not records:
            return None
        return {
            "days": [
                {
                    "date": str(r.date),
                    "total_energy_wh": round(r.total_energy_wh, 1),
                }
                for r in records
            ]
        }


@charts_blueprint.route("/daily")
def daily_chart():
    image = chart_service.generate_daily_chart()
    return _png_response(image)


@charts_blueprint.route("/multiday")
def multiday_chart():
    days = request.args.get("days", 7, type=int)
    days = min(days, 7)
    image = chart_service.generate_multi_day_chart(days)
    return _png_response(image)


@charts_blueprint.route("/monthly")
def monthly_chart():
    now = datetime.datetime.now()
    month = request.args.get("month", now.month, type=int)
    year = request.args.get("year", now.year, type=int)
    image = chart_service.generate_monthly_chart(month, year)
    return _png_response(image)


@charts_blueprint.route("/power-history")
def power_history_chart():
    hours = request.args.get("hours", 1, type=float)
    data = _get_power_history_data(hours)
    if data is None or not data.get("readings"):
        return jsonify({"error": "No power history available"}), 404
    image = ChartService.generate_power_history_chart(data)
    return _png_response(image)


@charts_blueprint.route("/daily-energy")
def daily_energy_chart():
    days = request.args.get("days", 30, type=int)
    data = _get_daily_energy_data(days)
    if data is None or not data.get("days"):
        return jsonify({"error": "No daily energy data available"}), 404
    image = ChartService.generate_daily_energy_chart(data)
    return _png_response(image)
