import datetime
import io
import logging

import matplotlib.pyplot as plt

from src.clients.growatt import GrowattClient

logger = logging.getLogger(__name__)


class ChartService:
    def __init__(self, growatt_client: GrowattClient) -> None:
        self._growatt = growatt_client

    def generate_daily_chart(self, ecoflow_hourly: dict | None = None) -> io.BytesIO:
        data = self._growatt.get_daily_chart_data(datetime.datetime.today())
        sorted_g = dict(sorted(data.items()))
        x_g = list(sorted_g.keys())
        y_g = [float(v) for v in sorted_g.values()]

        fig, ax = plt.subplots(figsize=(20, 12), dpi=300)
        ax.plot(x_g, y_g, marker="o", linestyle="-", label="Growatt Solar")

        if ecoflow_hourly:
            sorted_e = dict(sorted(ecoflow_hourly.items()))
            x_e = list(sorted_e.keys())
            y_e = list(sorted_e.values())
            ax.plot(x_e, y_e, marker="s", linestyle="--", label="EcoFlow Solar")

        ax.set_xlabel("Time")
        ax.set_ylabel("Wattage (W)")
        ax.set_title("Solar production over the day")
        ax.grid(True)
        ax.legend()
        plt.xticks(rotation=45)
        plt.locator_params(axis="y", nbins=10)

        image = io.BytesIO()
        plt.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    def generate_multi_day_chart(self, days: int, ecoflow_daily: dict | None = None) -> io.BytesIO:
        today = datetime.datetime.today()

        monthly_data = self._growatt.get_monthly_chart_data(today.year, today.month)
        sorted_monthly = dict(sorted(monthly_data.items()))

        extra_monthly: dict = {}
        first_day = today - datetime.timedelta(days=days - 1)
        if first_day.month != today.month:
            extra_data = self._growatt.get_monthly_chart_data(first_day.year, first_day.month)
            extra_monthly = dict(sorted(extra_data.items()))

        labels: list[str] = []
        growatt_vals: list[float] = []
        ecoflow_vals: list[float] = []

        for i in reversed(range(days)):
            target_date = today - datetime.timedelta(days=i)

            if i == 0:
                label = "Today"
            elif i == 1:
                label = "Yesterday"
            else:
                label = target_date.strftime("%A")

            day_str = f"{target_date.day:02d}"
            if extra_monthly and target_date.month != today.month:
                g_kwh = float(extra_monthly.get(day_str, 0))
            else:
                g_kwh = float(sorted_monthly.get(day_str, 0))

            e_kwh = float((ecoflow_daily or {}).get(target_date.date(), 0))

            labels.append(label)
            growatt_vals.append(g_kwh)
            ecoflow_vals.append(e_kwh)

        x = list(range(len(labels)))
        width = 0.35

        fig, ax = plt.subplots(figsize=(14, 8), dpi=300)
        ax.bar([i - width / 2 for i in x], growatt_vals, width, label="Growatt")
        ax.bar([i + width / 2 for i in x], ecoflow_vals, width, label="EcoFlow")

        ax.set_xlabel("Day")
        ax.set_ylabel("Energy (kWh)")
        ax.set_title("Daily solar production")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45)
        ax.grid(axis="y")
        ax.legend()

        image = io.BytesIO()
        plt.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    def generate_monthly_chart(self, month: int, year: int, ecoflow_monthly: dict | None = None) -> io.BytesIO:
        data = self._growatt.get_monthly_chart_data(year, month)
        sorted_g = dict(sorted(data.items()))

        all_days = sorted(set(sorted_g.keys()) | set((ecoflow_monthly or {}).keys()))
        growatt_vals = [float(sorted_g.get(d, 0)) for d in all_days]
        ecoflow_vals = [float((ecoflow_monthly or {}).get(d, 0)) for d in all_days]

        x = list(range(len(all_days)))
        width = 0.35

        fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
        ax.bar([i - width / 2 for i in x], growatt_vals, width, label="Growatt")
        ax.bar([i + width / 2 for i in x], ecoflow_vals, width, label="EcoFlow")

        date = datetime.date(year, month, 1)
        ax.set_xlabel("Date")
        ax.set_ylabel("kWh")
        ax.set_title(f"Solar production {date.strftime('%B %Y')}")
        ax.set_xticks(x)
        ax.set_xticklabels(all_days, rotation=45)
        ax.grid(axis="y")
        ax.legend()

        image = io.BytesIO()
        plt.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    @staticmethod
    def generate_power_history_chart(data: dict) -> io.BytesIO:
        readings = data.get("readings", [])
        times = [r["recorded_at"].split("T")[1][:5] for r in readings]
        pv1 = [r.get("pv1_power", 0) or 0 for r in readings]
        pv2 = [r.get("pv2_power", 0) or 0 for r in readings]
        grid = [r.get("grid_power", 0) or 0 for r in readings]

        fig, ax = plt.subplots(figsize=(20, 12), dpi=300)
        ax.plot(times, pv1, linestyle="-", label="PV1")
        ax.plot(times, pv2, linestyle="-", label="PV2")
        ax.plot(times, grid, linestyle="-", label="Grid")
        ax.set_xlabel("Time")
        ax.set_ylabel("Power (W)")
        ax.set_title("Power history")
        ax.grid(True)
        ax.legend()
        plt.xticks(rotation=45)
        plt.locator_params(axis="x", nbins=20)
        plt.locator_params(axis="y", nbins=10)

        image = io.BytesIO()
        plt.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    @staticmethod
    def generate_daily_energy_chart(data: dict) -> io.BytesIO:
        days = data.get("days", [])
        dates = [d["date"] for d in reversed(days)]
        totals = [d.get("total_energy_wh", 0) / 1000.0 for d in reversed(days)]

        fig = plt.figure(figsize=(14, 7), dpi=300)
        plt.bar(dates, totals, width=0.6)
        plt.xlabel("Date")
        plt.ylabel("Energy (kWh)")
        plt.title("Daily energy production")
        plt.xticks(rotation=45)
        plt.locator_params(axis="y", nbins=10)
        plt.grid(axis="y")

        image = io.BytesIO()
        plt.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image
