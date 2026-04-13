import datetime
import io
import logging

import matplotlib.pyplot as plt

from src.clients.growatt import GrowattClient

logger = logging.getLogger(__name__)


class ChartService:
    def __init__(self, growatt_client: GrowattClient) -> None:
        self._growatt = growatt_client

    def generate_daily_chart(self) -> io.BytesIO:
        data = self._growatt.get_daily_chart_data(datetime.datetime.today())
        sorted_data = dict(sorted(data.items()))
        x_values = list(sorted_data.keys())
        y_values = [float(v) for v in sorted_data.values()]

        fig, ax = plt.subplots(figsize=(20, 12), dpi=300)
        ax.plot(x_values, y_values, marker="o", linestyle="-")
        ax.set_xlabel("Time")
        ax.set_ylabel("Wattage (W)")
        ax.set_title("Power production over the day")
        ax.grid(True)
        plt.xticks(rotation=45)
        plt.locator_params(axis="y", nbins=10)

        image = io.BytesIO()
        plt.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    def generate_multi_day_chart(self, days: int) -> io.BytesIO:
        fig, ax = plt.subplots(figsize=(20, 12), dpi=300)
        today = datetime.datetime.today()

        monthly_data = self._growatt.get_monthly_chart_data(today.year, today.month)
        sorted_monthly = dict(sorted(monthly_data.items()))

        extra_monthly: dict = {}
        first_day = today - datetime.timedelta(days=days)
        if first_day.month != today.month:
            extra_data = self._growatt.get_monthly_chart_data(first_day.year, first_day.month)
            extra_monthly = dict(sorted(extra_data.items()))

        for i in reversed(range(days)):
            target_date = today - datetime.timedelta(days=i)

            if i == 0:
                name = "Today"
            elif i == 1:
                name = "Yesterday"
            else:
                name = target_date.strftime("%A")

            day_str = f"{target_date.day:02d}"

            if extra_monthly and target_date.month != today.month:
                daily_kwh = extra_monthly.get(day_str, 0)
            else:
                daily_kwh = sorted_monthly.get(day_str, 0)

            name = f"{name}  {daily_kwh} KwH"

            hourly_data = self._growatt.get_daily_chart_data(target_date)
            sorted_hourly = dict(sorted(hourly_data.items()))
            x_values = list(sorted_hourly.keys())
            y_values = [float(v) for v in sorted_hourly.values()]

            ax.plot(x_values, y_values, marker="o", linestyle="-", label=name)

        ax.set_xlabel("Time")
        ax.set_ylabel("Wattage (W)")
        ax.set_title("Power production over the day")
        ax.grid(True)
        ax.legend()
        plt.xticks(rotation=45)
        plt.locator_params(axis="y", nbins=10)

        image = io.BytesIO()
        plt.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    def generate_monthly_chart(self, month: int, year: int) -> io.BytesIO:
        data = self._growatt.get_monthly_chart_data(year, month)
        sorted_data = dict(sorted(data.items()))
        x_values = list(sorted_data.keys())
        y_values = [float(v) for v in sorted_data.values()]

        fig = plt.figure(figsize=(10, 5))
        plt.bar(x_values, y_values, width=0.4)

        date = datetime.date(year, month, 1)
        plt.xlabel("Date")
        plt.ylabel("KWH")
        plt.title(f"Power production {date.strftime('%B %Y')} over the month")
        plt.xticks(rotation=45)
        plt.locator_params(axis="y", nbins=10)
        plt.grid(axis="y")

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
