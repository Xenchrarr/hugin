import hashlib
import hmac
import random
import time
import logging
from datetime import datetime, timezone, timedelta

import requests
from flatten_dict import flatten
from urllib.parse import urlencode
from urllib.parse import unquote, quote
from http.client import HTTPConnection



class EcoflowClient:
    base_url = None
    access_key = None
    secret_key = None
    log = None
    _app_debug_level = None
    _requests_debug_level = None


    def __init__(self, access_key: str, secret_key: str, base_url: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.log = logging



    def set_logger(self, logger):
        self.log = logger


    def debug_requests_on(self):
        # (c) https://stackoverflow.com/a/24588289/741782
        '''Switches on logging of the requests module.'''
        HTTPConnection.debuglevel = 1

        self.log.basicConfig()
        root_logger = self.log.getLogger()
        self._app_debug_level = root_logger.getEffectiveLevel()
        root_logger.setLevel(self.log.DEBUG)

        requests_log = self.log.getLogger('requests.packages.urllib3')
        self._requests_debug_level = requests_log.getEffectiveLevel()
        requests_log.setLevel(self.log.DEBUG)
        requests_log.propagate = True

    def debug_requests_off(self):
        # (c) https://stackoverflow.com/a/24588289/741782
        '''Switches off logging of the requests module, might be some side-effects'''
        HTTPConnection.debuglevel = 0

        self.log.getLogger().setLevel(self._app_debug_level)

        requests_log = self.log.getLogger('requests.packages.urllib3')
        requests_log.setLevel(self._requests_debug_level)
        requests_log.propagate = False




    def get_timestamp(self):
        timestamp = int(time.time()) * 1000
        return str(timestamp)

    def generate_nonce(self):
        return str(random.randrange(100000, 999999))

    def ecoflow_reducer(self, k1, k2):
        if k1 is None:
            return k2
        else:
            if type(k2) is int:
                return f"{k1}[{k2}]"
            else:
                return f"{k1}.{k2}"




    def request(self, method, url, *, data=None, query_params=None):
        timestamp = self.get_timestamp()
        nonce = self.generate_nonce()

        sign_params = {**(query_params or {}), **(data or {})}

        headers = {
            'accessKey': self.access_key,
            'nonce': nonce,
            'timestamp': timestamp,
            'sign': self.generate_sign(sign_params, timestamp, nonce)
        }

        if data is not None:
            headers['Content-Type'] = 'application/json;charset=UTF-8'

        response = requests.request(method, url, headers=headers, json=data, params=query_params, timeout=(10, 30))

        self.debug(f"{method} {url} -> {response.status_code}")

        if response and response.status_code == 200:
            return response
        else:
            self.error(f"Non-success status code: {response.status_code} while requesting {url}")
            raise Exception(f"Non-success status code: {response.status_code}")

    def get_device_quota(self, sn, params):
        """
        Query the device's quota infomation
        """

        data = {
            'params': params,
            'sn': sn
        }

        return self.request('post', self.url('/iot-open/sign/device/quota'), data = data)


    def generate_sign(self, params, timestamp, nonce):
        params = flatten(params, reducer = self.ecoflow_reducer, enumerate_types=(list,))
        sorted_params = sorted(params.items())
        sorted_params.extend([
            ('accessKey', self.access_key),
            ('nonce', nonce),
            ('timestamp', timestamp),
        ])

        return hmac \
            .new(self.secret_key.encode(), unquote(urlencode(sorted_params, quote_via=quote)).encode(), hashlib.sha256) \
            .hexdigest()


    def url(self, path_and_params):
        return f"{self.base_url}{path_and_params}"

    def debug(self, message):
        self.log.debug(f"Ecoflow API debug: {message}")
        pass

    def error(self, message):
        self.log.error(f"Ecoflow API error occured: {message}")
        pass


    def get_device_list(self):
        """
        Query the user's bound device list
        Only returns the device bound to itself, not by share.
        """

        return self.request('get', self.url('/iot-open/sign/device/list'))

    def get_mqtt_certification(self):
        """
        Get MQTT credentials for real-time device communication.
        Returns certificateAccount, certificatePassword, url, port, protocol.
        """
        return self.request('get', self.url('/iot-open/sign/certification'))

    def get_main_sn(self, sn: str):
        """
        Get the main device serial number for a STREAM BKW system.
        Required before calling most STREAM endpoints.
        """
        return self.request('get', self.url('/iot-open/sign/device/system/main/sn'), query_params={'sn': sn})

    def get_all_quota(self, sn: str):
        """
        Get all real-time quota data for a device.
        Returns powGetPvSum (current PV power W), cmsBattSoc (battery %),
        powGetSysLoad (load W), gridConnectionPower, etc.
        """
        return self.request('get', self.url('/iot-open/sign/device/quota/all'), query_params={'sn': sn})

    def get_historical_data(self, sn: str, begin_time: str, end_time: str, code: str):
        """
        Query historical data for a device.
        Times must be UTC formatted as 'yyyy-MM-dd HH:mm:ss'.
        """
        data = {
            'sn': sn,
            'params': {
                'beginTime': begin_time,
                'endTime': end_time,
                'code': code,
            }
        }
        return self.request('post', self.url('/iot-open/sign/device/quota/data'), data=data)

    def get_today_solar_production(self, sn: str):
        """
        Get today's total solar energy production in Wh (UTC day boundaries).
        """
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        return self.get_historical_data(
            sn,
            begin_time=f"{today} 00:00:00",
            end_time=f"{today} 23:59:59",
            code='BK621-App-HOME-SOLAR-ENERGY-FLOW-solor-line-NOTDISTINGUISH-MASTER_DATA',
        )

    def get_yesterday_solar_production(self, sn: str):
        """
        Get yesterday's total solar energy production in Wh (UTC day boundaries).
        """
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
        return self.get_historical_data(
            sn,
            begin_time=f"{yesterday} 00:00:00",
            end_time=f"{yesterday} 23:59:59",
            code='BK621-App-HOME-SOLAR-ENERGY-FLOW-solor-line-NOTDISTINGUISH-MASTER_DATA',
        )