#!/usr/bin/env python3
"""
Minimal Deye debug runner.

Usage:
    python main.py data                     # current inverter snapshot
    python main.py chart [YYYY-MM-DD]       # hourly production (default: today)
    python main.py chart-month [YYYY-MM]    # daily production for a month (default: this month)
    python main.py raw                      # raw API response for current data (debugging keys)

Credentials are read from a .env file in this directory.
Copy .env.example to .env and fill in the values.
"""

import datetime
import json
import logging
import os
import sys

from dotenv import load_dotenv

from deye_client import DeyeClient

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)

# Silence noisy urllib3/requests debug lines – keep our own logs visible
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


def _build_client() -> DeyeClient:
    required = {
        "DEYE_APP_ID": os.environ.get("DEYE_APP_ID", ""),
        "DEYE_APP_SECRET": os.environ.get("DEYE_APP_SECRET", ""),
        "DEYE_EMAIL": os.environ.get("DEYE_EMAIL", ""),
        "DEYE_PASSWORD": os.environ.get("DEYE_PASSWORD", ""),
        "DEYE_DEVICE_SN": os.environ.get("DEYE_DEVICE_SN", ""),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"ERROR: Missing credentials in .env: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    return DeyeClient(
        app_id=required["DEYE_APP_ID"],
        app_secret=required["DEYE_APP_SECRET"],
        email=required["DEYE_EMAIL"],
        password=required["DEYE_PASSWORD"],
        device_sn=required["DEYE_DEVICE_SN"],
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_data() -> None:
    """Fetch and display the current inverter snapshot."""
    client = _build_client()
    print("Fetching current inverter data…")
    result = client.get_inverter_data()
    if result is None:
        print("ERROR: No data returned (check credentials and device SN)")
        sys.exit(1)

    raw = result.pop("_raw", None)

    print()
    print(f"  Current power : {result.get('currentPower', 'N/A')}")
    print(f"  Today's yield : {result.get('todayEnergy', 'N/A')} kWh")
    print(f"  Monthly yield : {result.get('monthlyEnergy', 'N/A')} kWh")
    print(f"  Total yield   : {result.get('totalEnergy', 'N/A')} kWh")

    if raw:
        print()
        print("  Raw dataList keys returned by API:")
        for item in raw.get("dataList", []):
            print(f"    {item.get('key', '?'):40s}  {item.get('value', '')} {item.get('unit', '')}")


def cmd_chart(date_str: str | None) -> None:
    """Fetch and display hourly production for a single day."""
    if date_str:
        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            print(f"ERROR: Invalid date '{date_str}' — expected YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
    else:
        date = datetime.date.today()

    client = _build_client()
    print(f"Fetching hourly chart data for {date}…")
    data = client.get_daily_chart_data(date)

    if not data:
        print("No data returned (device may be offline or date too old)")
        return

    print()
    print(f"  Hourly production — {date}")
    print(f"  {'Hour':>8}  {'Wh / W':>10}")
    print(f"  {'-'*8}  {'-'*10}")
    for hour in sorted(data):
        bar = "█" * int(data[hour] / 50)
        print(f"  {hour:>8}  {data[hour]:>10.1f}  {bar}")


def cmd_chart_month(month_str: str | None) -> None:
    """Fetch and display daily production for a month."""
    if month_str:
        try:
            parts = month_str.split("-")
            year, month = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            print(f"ERROR: Invalid month '{month_str}' — expected YYYY-MM", file=sys.stderr)
            sys.exit(1)
    else:
        today = datetime.date.today()
        year, month = today.year, today.month

    client = _build_client()
    print(f"Fetching daily chart data for {year}-{month:02d}…")
    data = client.get_monthly_chart_data(year, month)

    if not data:
        print("No data returned")
        return

    total = sum(data.values())
    print()
    print(f"  Daily production — {year}-{month:02d}  (total {total:.2f} kWh)")
    print(f"  {'Day':>5}  {'kWh':>8}")
    print(f"  {'-'*5}  {'-'*8}")
    for day in sorted(data):
        bar = "█" * int(data[day] / 0.5)
        print(f"  {day:>5}  {data[day]:>8.3f}  {bar}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

COMMANDS = {
    "data": (cmd_data, "Current inverter snapshot"),
    "chart": (cmd_chart, "Hourly production for a day (optionally pass YYYY-MM-DD)"),
    "chart-month": (cmd_chart_month, "Daily production for a month (optionally pass YYYY-MM)"),
}


def usage() -> None:
    print("Usage:")
    for name, (_, desc) in COMMANDS.items():
        print(f"  python main.py {name:<14}  {desc}")
    sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        usage()

    command = args[0]

    if command == "data":
        cmd_data()
    elif command == "chart":
        cmd_chart(args[1] if len(args) > 1 else None)
    elif command == "chart-month":
        cmd_chart_month(args[1] if len(args) > 1 else None)
    else:
        print(f"Unknown command: {command!r}\n")
        usage()
