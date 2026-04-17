import os

import requests

CORE_API_URL = os.environ.get("CORE_API_URL", "http://hugin-core:5100")

session = requests.Session()
