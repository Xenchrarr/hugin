import datetime
import hashlib
import logging

import requests

logger = logging.getLogger(__name__)

_CLOUD_BASE = "https://globalapi.solarmanpv.com"


class DeyeClient:
    """Client for the Deye / SolarMan cloud REST API.

    Requires a SolarMan developer App ID and App Secret (obtained from
    https://home.solarmanpv.com/developer), plus the account credentials
    and the logger device serial number shown in the SolarMan app.
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        email: str,
        password: str,
        device_sn: str,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._email = email
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()
        self._device_sn = device_sn

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_token(self) -> str | None:
        """Obtain a short-lived Bearer token from SolarMan."""
        url = f"{_CLOUD_BASE}/account/v1.0/token?appId={self._app_id}&language=en"
        body = {
            "appSecret": self._app_secret,
            "email": self._email,
            "password": self._password_hash,
        }
        try:
            resp = requests.post(url, json=body, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success", True) is False and data.get("access_token"):
                return data["access_token"]
            # Some API versions wrap in code/msg
            if data.get("code") == "0" or data.get("returnCode") == 0:
                return data.get("access_token") or data.get("data", {}).get("access_token")
            logger.error("DeyeClient: token request failed: %s", data)
            return None
        except Exception:
            logger.exception("DeyeClient: token request error")
            return None

    def _auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_inverter_data(self) -> dict | None:
        """Return current inverter snapshot.

        Returns a dict with keys matching the Growatt response shape:
          currentPower, todayEnergy, totalEnergy, monthlyEnergy
        """
        token = self._get_token()
        if not token:
            return None

        url = f"{_CLOUD_BASE}/device/v1.0/currentData?language=en"
        body = {"deviceSn": self._device_sn}
        try:
            resp = requests.post(url, json=body, headers=self._auth_headers(token), timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.exception("DeyeClient: get_inverter_data error")
            return None

        data_list: list[dict] = data.get("dataList", [])
        values: dict[str, str] = {item["key"]: item.get("value", "0") for item in data_list}

        current_power = values.get("generation_power") or values.get("total_active_power", "0")
        today_energy = values.get("daily_production") or values.get("today_production", "0")
        total_energy = values.get("total_production") or values.get("cumulative_production", "0")
        monthly_energy = values.get("monthly_production", "0")

        return {
            "currentPower": f"{current_power}W",
            "todayEnergy": today_energy,
            "totalEnergy": total_energy,
            "monthlyEnergy": monthly_energy,
        }

    def get_daily_chart_data(self, date: datetime.date) -> dict:
        """Return hourly production for a single day as {"HH:00": kWh_float, ...}."""
        token = self._get_token()
        if not token:
            return {}

        start_ts = int(datetime.datetime(date.year, date.month, date.day, 0, 0, 0).timestamp())
        end_ts = int(datetime.datetime(date.year, date.month, date.day, 23, 59, 59).timestamp())

        url = f"{_CLOUD_BASE}/device/v1.0/historical?language=en"
        body = {
            "deviceSn": self._device_sn,
            "startTime": start_ts,
            "endTime": end_ts,
            "timeType": 3,  # hourly
        }
        try:
            resp = requests.post(url, json=body, headers=self._auth_headers(token), timeout=15)
            resp.raise_for_status()
            raw = resp.json()
        except Exception:
            logger.exception("DeyeClient: get_daily_chart_data error")
            return {}

        return self._parse_historical_hourly(raw)

    def get_monthly_chart_data(self, year: int, month: int) -> dict:
        """Return daily production for a month as {"DD": kWh_float, ...}."""
        token = self._get_token()
        if not token:
            return {}

        start_dt = datetime.date(year, month, 1)
        if month == 12:
            end_dt = datetime.date(year + 1, 1, 1)
        else:
            end_dt = datetime.date(year, month + 1, 1)
        start_ts = int(datetime.datetime(start_dt.year, start_dt.month, start_dt.day).timestamp())
        end_ts = int(datetime.datetime(end_dt.year, end_dt.month, end_dt.day).timestamp()) - 1

        url = f"{_CLOUD_BASE}/device/v1.0/historical?language=en"
        body = {
            "deviceSn": self._device_sn,
            "startTime": start_ts,
            "endTime": end_ts,
            "timeType": 4,  # daily
        }
        try:
            resp = requests.post(url, json=body, headers=self._auth_headers(token), timeout=15)
            resp.raise_for_status()
            raw = resp.json()
        except Exception:
            logger.exception("DeyeClient: get_monthly_chart_data error")
            return {}

        return self._parse_historical_daily(raw)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_historical_hourly(raw: dict) -> dict:
        """
        The SolarMan cloud API returns historical data in the dataList field.
        Each entry has a "collectTime" (unix timestamp) and data key/value pairs.
        We extract the production energy value per hour.
        """
        result: dict[str, float] = {}
        for entry in raw.get("dataList", []):
            ts = entry.get("collectTime")
            if ts is None:
                continue
            dt = datetime.datetime.fromtimestamp(int(ts))
            hour_label = dt.strftime("%H:00")
            # Look for production energy key
            values: dict[str, str] = {item["key"]: item.get("value", "0") for item in entry.get("dataList", [])}
            production = values.get("generation_power") or values.get("total_active_power", "0")
            try:
                result[hour_label] = float(production)
            except (ValueError, TypeError):
                result[hour_label] = 0.0
        return result

    @staticmethod
    def _parse_historical_daily(raw: dict) -> dict:
        """
        Daily history — extract one kWh value per day, keyed as zero-padded "DD".
        """
        result: dict[str, float] = {}
        for entry in raw.get("dataList", []):
            ts = entry.get("collectTime")
            if ts is None:
                continue
            dt = datetime.datetime.fromtimestamp(int(ts))
            day_label = f"{dt.day:02d}"
            values: dict[str, str] = {item["key"]: item.get("value", "0") for item in entry.get("dataList", [])}
            production = values.get("daily_production") or values.get("today_production", "0")
            try:
                result[day_label] = float(production)
            except (ValueError, TypeError):
                result[day_label] = 0.0
        return result
