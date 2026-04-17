import os

import requests

TELEGRAM_BOT_URL = os.environ.get("TELEGRAM_BOT_URL", "http://overlia-power-bot:5060")

session = requests.Session()
