import logging
import re
from datetime import datetime, timezone

import cairosvg
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.yr.no/en/content/{yr_id}/meteogram.svg"
YR_LOCATION_API = "https://www.yr.no/api/v0/locations/{yr_id}"
MET_FORECAST_API = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
_HEADERS = {"User-Agent": "hugin-bot/1.0 github.com/hugin"}

_SYMBOL_LABELS: dict[str, str] = {
    "clearsky": "clear sky",
    "fair": "fair",
    "partlycloudy": "partly cloudy",
    "cloudy": "cloudy",
    "fog": "fog",
    "lightrainshowers": "light rain showers",
    "rainshowers": "rain showers",
    "heavyrainshowers": "heavy rain showers",
    "lightrain": "light rain",
    "rain": "rain",
    "heavyrain": "heavy rain",
    "lightsleet": "light sleet",
    "sleet": "sleet",
    "heavysleet": "heavy sleet",
    "lightsnowshowers": "light snow showers",
    "snowshowers": "snow showers",
    "lightsnow": "light snow",
    "snow": "snow",
    "heavysnow": "heavy snow",
    "thunderstorm": "thunderstorm",
    "sleetandthunder": "sleet and thunder",
    "snowandthunder": "snow and thunder",
}


def _symbol_label(code: str) -> str:
    """Convert a met.no symbol_code like 'partlycloudy_day' to a readable label."""
    base = code.split("_")[0]
    return _SYMBOL_LABELS.get(base, base.replace("_", " "))


class YrClient:
    def get_weather_summary(self, yr_id: str) -> dict | None:
        """Return a short text weather summary for the given yr_id."""
        try:
            loc_resp = requests.get(
                YR_LOCATION_API.format(yr_id=yr_id),
                headers=_HEADERS,
                timeout=(5, 10),
            )
            if loc_resp.status_code != 200:
                logger.error("yr.no location lookup failed: %s", loc_resp.status_code)
                return None
            loc = loc_resp.json()
            position = loc.get("position") or loc.get("location", {}).get("position", {})
            lat = position.get("lat")
            lon = position.get("lon")
            if lat is None or lon is None:
                logger.error("No lat/lon in yr.no location response: %s", loc)
                return None
        except Exception:
            logger.exception("Error resolving yr_id %s to lat/lon", yr_id)
            return None

        try:
            fc_resp = requests.get(
                MET_FORECAST_API,
                params={"lat": round(lat, 4), "lon": round(lon, 4)},
                headers=_HEADERS,
                timeout=(5, 15),
            )
            if fc_resp.status_code != 200:
                logger.error("MET forecast API failed: %s", fc_resp.status_code)
                return None
            fc = fc_resp.json()
        except Exception:
            logger.exception("Error fetching MET forecast for %s", yr_id)
            return None

        try:
            series = fc["properties"]["timeseries"]
            now_entry = series[0]
            now_instant = now_entry["data"]["instant"]["details"]
            temp = round(now_instant.get("air_temperature", 0), 1)
            wind = round(now_instant.get("wind_speed", 0), 1)

            next1h = now_entry["data"].get("next_1_hours") or now_entry["data"].get("next_6_hours", {})
            symbol = _symbol_label(next1h.get("summary", {}).get("symbol_code", ""))
            precip = next1h.get("details", {}).get("precipitation_amount", 0)

            # Find entry ~6 hours ahead for a short outlook
            now_dt = datetime.fromisoformat(now_entry["time"].replace("Z", "+00:00"))
            outlook_parts: list[str] = []
            for entry in series[1:7]:
                entry_dt = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
                delta_h = (entry_dt - now_dt).total_seconds() / 3600
                if delta_h >= 5:
                    outlook_instant = entry["data"]["instant"]["details"]
                    outlook_temp = round(outlook_instant.get("air_temperature", 0), 1)
                    next_block = entry["data"].get("next_6_hours") or entry["data"].get("next_1_hours", {})
                    outlook_sym = _symbol_label(next_block.get("summary", {}).get("symbol_code", ""))
                    outlook_precip = next_block.get("details", {}).get("precipitation_amount", 0)
                    hour_label = entry_dt.astimezone(timezone.utc).strftime("%H:00")
                    p = f"{hour_label}: {outlook_temp}°C {outlook_sym}"
                    if outlook_precip:
                        p += f", {outlook_precip}mm"
                    outlook_parts.append(p)
                    break

            text = f"Now: {temp}°C {symbol}, wind {wind} m/s"
            if precip:
                text += f", {precip}mm"
            if outlook_parts:
                text += " | " + " | ".join(outlook_parts)

            return {"text": text}
        except Exception:
            logger.exception("Error parsing MET forecast response")
            return None

    def get_weather_image(self, yr_id: str, dark_mode: bool = True) -> bytes | None:
        try:
            mode = "dark" if dark_mode else "light"
            url = BASE_URL.format(yr_id=yr_id) + f"?mode={mode}"
            response = requests.get(url, timeout=(5, 15))

            if response.status_code == 200:
                return self._convert_svg_to_png(response.content)
            else:
                logger.error("Failed to download weather image. Status code: %s", response.status_code)
                return None
        except Exception:
            logger.exception("Error downloading weather image")
            return None

    @staticmethod
    def _convert_svg_to_png(svg_content: bytes) -> bytes | None:
        try:
            svg_str = re.sub(
                r"(\d*\.?\d+)rem",
                lambda m: f"{float(m.group(1)) * 16}px",
                svg_content.decode("utf-8"),
            )
            return cairosvg.svg2png(bytestring=svg_str)
        except Exception:
            logger.exception("Error converting SVG to PNG")
            return None
