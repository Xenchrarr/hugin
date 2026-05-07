import datetime
from collections import defaultdict
from datetime import timedelta

import pytz
from flask import Blueprint, Response, jsonify, request
from sqlalchemy import desc

from src.clients.deye import DeyeClient
from src.clients.growatt import GrowattClient
from src.database import get_session
from src.models.power import PowerReading, DailyEnergy
from src.services.chart_service import ChartService
from src.services.user_config_service import get_primary_user_config

charts_blueprint = Blueprint("charts", __name__)

_LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo


def _get_ecoflow_hourly_for_date(date: datetime.date) -> dict[str, float]:
    """Return {HH:00 label: avg_combined_pv_watts} for a given local date."""
    day_start = datetime.datetime(date.year, date.month, date.day, tzinfo=_LOCAL_TZ).astimezone(pytz.UTC)
    day_end = day_start + timedelta(days=1)
    buckets: dict[str, list] = defaultdict(list)
    with get_session() as session:
        readings = (
            session.query(PowerReading)
            .filter(PowerReading.recorded_at >= day_start, PowerReading.recorded_at < day_end)
            .order_by(PowerReading.recorded_at.asc())
            .all()
        )
        for r in readings:
            local_ts = r.recorded_at.astimezone(_LOCAL_TZ)
            hour_label = local_ts.strftime("%H:00")
            buckets[hour_label].append((r.pv1_power or 0) + (r.pv2_power or 0))
    return {hour: round(sum(vals) / len(vals), 1) for hour, vals in buckets.items()}


def _get_ecoflow_kwh_for_dates(dates: list[datetime.date]) -> dict[datetime.date, float]:
    """Return {date: total_kwh} for the given list of dates."""
    with get_session() as session:
        records = (
            session.query(DailyEnergy)
            .filter(DailyEnergy.date.in_(dates))
            .all()
        )
        return {r.date: round(r.total_energy_wh / 1000.0, 2) for r in records}


def _get_ecoflow_monthly_kwh(month: int, year: int) -> dict[str, float]:
    """Return {DD day string: total_kwh} for the given month/year."""
    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)
    with get_session() as session:
        records = (
            session.query(DailyEnergy)
            .filter(DailyEnergy.date >= month_start, DailyEnergy.date < month_end)
            .all()
        )
        return {f"{r.date.day:02d}": round(r.total_energy_wh / 1000.0, 2) for r in records}


def _get_chart_service() -> tuple[ChartService, tuple[dict, int] | None]:
    """Build a ChartService backed by per-request Growatt credentials.

    Returns (chart_service, None) on success, or (None, error_response_tuple) on failure.
    """
    try:
        config = get_primary_user_config()
    except RuntimeError as e:
        return None, ({"error": f"Could not fetch user config: {e}"}, 503)

    username = config.get("growatt_username", "")
    password = config.get("growatt_password", "")
    if not username or not password:
        return None, ({"error": "Growatt credentials not configured in user settings"}, 503)

    deye_client: DeyeClient | None = None
    deye_app_id = config.get("deye_app_id", "")
    deye_app_secret = config.get("deye_app_secret", "")
    deye_email = config.get("deye_email", "")
    deye_password = config.get("deye_password", "")
    deye_device_sn = config.get("deye_device_sn", "")
    if all([deye_app_id, deye_app_secret, deye_email, deye_password, deye_device_sn]):
        deye_client = DeyeClient(deye_app_id, deye_app_secret, deye_email, deye_password, deye_device_sn)

    return ChartService(GrowattClient(username, password), deye_client=deye_client), None


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
    chart_service, err = _get_chart_service()
    if err:
        return jsonify(err[0]), err[1]
    ecoflow_hourly = _get_ecoflow_hourly_for_date(datetime.date.today())
    image = chart_service.generate_daily_chart(ecoflow_hourly=ecoflow_hourly or None)
    return _png_response(image)


@charts_blueprint.route("/multiday")
def multiday_chart():
    chart_service, err = _get_chart_service()
    if err:
        return jsonify(err[0]), err[1]
    days = min(request.args.get("days", 7, type=int), 7)
    today = datetime.date.today()
    dates = [today - timedelta(days=i) for i in range(days)]
    ecoflow_daily = _get_ecoflow_kwh_for_dates(dates)
    image = chart_service.generate_multi_day_chart(days, ecoflow_daily=ecoflow_daily)
    return _png_response(image)


@charts_blueprint.route("/monthly")
def monthly_chart():
    chart_service, err = _get_chart_service()
    if err:
        return jsonify(err[0]), err[1]
    now = datetime.datetime.now()
    month = request.args.get("month", now.month, type=int)
    year = request.args.get("year", now.year, type=int)
    ecoflow_monthly = _get_ecoflow_monthly_kwh(month, year)
    image = chart_service.generate_monthly_chart(month, year, ecoflow_monthly=ecoflow_monthly)
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
