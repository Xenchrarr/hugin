import datetime
import logging

import growattServer
from growattServer import Timespan

from src.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = "ShinePhone/8.1.17 (iPhone; iOS 15.6.1; Scale/2.00)"


class GrowattClient:
    def __init__(self) -> None:
        self._username = settings.GROWATT_USERNAME
        self._password = settings.GROWATT_PASSWORD

    def _get_api(self) -> growattServer.GrowattApi:
        return growattServer.GrowattApi(agent_identifier=USER_AGENT)

    def _login(self) -> tuple[growattServer.GrowattApi, dict] | None:
        api = self._get_api()
        login_response = api.login(self._username, self._password)
        if not login_response["success"]:
            logger.error("Growatt login failed")
            return None
        return api, login_response

    def _get_plant_id(self, api: growattServer.GrowattApi, login_response: dict) -> str:
        plant_list = api.plant_list(login_response["user"]["id"])
        return plant_list["data"][0]["plantId"]

    def get_inverter_data(self) -> dict | None:
        result = self._login()
        if result is None:
            return None
        api, login_response = result
        plant_list = api.plant_list(login_response["user"]["id"])
        data = plant_list["data"][0]
        data["currentPower"] = api.device_list(data["plantId"])[0]["power"] + "W"
        return data

    def get_daily_chart_data(self, date: datetime.date) -> dict:
        result = self._login()
        if result is None:
            return {}
        api, login_response = result
        plant_id = self._get_plant_id(api, login_response)
        return api.plant_detail(plant_id, Timespan.day, date)["data"]

    def get_monthly_chart_data(self, year: int, month: int) -> dict:
        date = datetime.date(year, month, 1)
        result = self._login()
        if result is None:
            return {}
        api, login_response = result
        plant_id = self._get_plant_id(api, login_response)
        return api.plant_detail(plant_id, Timespan.month, date)["data"]
