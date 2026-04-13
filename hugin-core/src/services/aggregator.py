import logging
from datetime import datetime, timedelta, date

import pytz
from sqlalchemy import func

from src.config import settings
from src.database import get_session
from src.models.power import PowerReading, DailyEnergy

log = logging.getLogger(__name__)


def aggregate_day(target_date: date):
    tz = pytz.timezone(settings.TIMEZONE)
    day_start = tz.localize(datetime.combine(target_date, datetime.min.time()))
    day_end = day_start + timedelta(days=1)

    with get_session() as session:
        readings = (
            session.query(PowerReading)
            .filter(PowerReading.recorded_at >= day_start)
            .filter(PowerReading.recorded_at < day_end)
            .order_by(PowerReading.recorded_at.asc())
            .all()
        )

        if len(readings) < 2:
            log.info(f"Not enough readings for {target_date} ({len(readings)} found)")
            return

        pv1_energy = 0.0
        pv2_energy = 0.0
        grid_energy = 0.0
        pv1_max = 0.0
        pv2_max = 0.0
        grid_max = 0.0

        for i in range(1, len(readings)):
            prev = readings[i - 1]
            curr = readings[i]

            dt_hours = (curr.recorded_at - prev.recorded_at).total_seconds() / 3600.0

            max_gap = 90.0 / 60.0 if (prev.grid_power or 0) >= 70 else 10.0 / 60.0
            if dt_hours > max_gap:
                continue

            p1_prev = prev.pv1_power or 0.0
            p1_curr = curr.pv1_power or 0.0
            pv1_energy += (p1_prev + p1_curr) / 2.0 * dt_hours

            p2_prev = prev.pv2_power or 0.0
            p2_curr = curr.pv2_power or 0.0
            pv2_energy += (p2_prev + p2_curr) / 2.0 * dt_hours

            g_prev = prev.grid_power or 0.0
            g_curr = curr.grid_power or 0.0
            grid_energy += (g_prev + g_curr) / 2.0 * dt_hours

            pv1_max = max(pv1_max, p1_curr)
            pv2_max = max(pv2_max, p2_curr)
            grid_max = max(grid_max, g_curr)

        total_energy = pv1_energy + pv2_energy

        existing = session.query(DailyEnergy).filter(DailyEnergy.date == target_date).first()
        if existing:
            existing.pv1_energy_wh = pv1_energy
            existing.pv2_energy_wh = pv2_energy
            existing.total_energy_wh = total_energy
            existing.grid_energy_wh = grid_energy
            existing.pv1_max_power = pv1_max
            existing.pv2_max_power = pv2_max
            existing.grid_max_power = grid_max
            existing.reading_count = len(readings)
            existing.updated_at = func.now()
        else:
            session.add(DailyEnergy(
                date=target_date,
                pv1_energy_wh=pv1_energy,
                pv2_energy_wh=pv2_energy,
                total_energy_wh=total_energy,
                grid_energy_wh=grid_energy,
                pv1_max_power=pv1_max,
                pv2_max_power=pv2_max,
                grid_max_power=grid_max,
                reading_count=len(readings),
            ))

        log.info(
            f"Aggregated {target_date}: "
            f"PV1={pv1_energy:.1f}Wh PV2={pv2_energy:.1f}Wh "
            f"Total={total_energy:.1f}Wh Grid={grid_energy:.1f}Wh "
            f"({len(readings)} readings)"
        )


def run_aggregation():
    tz = pytz.timezone(settings.TIMEZONE)
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)

    log.info(f"Running aggregation for {yesterday} and {today}")
    aggregate_day(yesterday)
    aggregate_day(today)
