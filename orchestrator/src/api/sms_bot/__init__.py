import os

import requests

SMS_BOT_URL = os.environ.get("SMS_BOT_URL", "http://sms-hub:5050")

session = requests.Session()
