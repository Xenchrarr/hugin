import requests

from src.config import HUGIN_CORE_URL, YR_ID
from src.services.print_service import PrintService


class WeatherService:
    def __init__(self):
        self.print_service = PrintService()

    def fetch_and_print(self, yr_id: str = None) -> dict:
        location_id = yr_id or YR_ID
        if not location_id:
            raise Exception("No yr_id provided and YR_ID env var is not set")

        url = f"{HUGIN_CORE_URL}/api/weather/{location_id}"
        response = requests.get(url, params={"dark": "false"}, timeout=(5, 20))

        if response.status_code != 200:
            raise Exception(f"Failed to fetch weather image: {response.status_code}")

        self.print_service.print_image(response.content)

        return {"status": "printed", "yr_id": location_id}
