import os

import requests
from requests.adapters import HTTPAdapter

PRINTER_HUB_URL = os.environ.get("PRINTER_HUB_URL", "http://printer-hub:6002")
PRINTER_HUB_TIMEOUT = int(os.environ.get("PRINTER_HUB_TIMEOUT", "60"))

session = requests.Session()
adapter = HTTPAdapter(pool_connections=1, pool_maxsize=5)
session.mount('http://', adapter)
session.mount('https://', adapter)
