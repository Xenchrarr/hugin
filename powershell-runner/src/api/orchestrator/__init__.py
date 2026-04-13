import os

import requests
from requests.adapters import HTTPAdapter

ORCHESTRATOR_BASE_URL = os.environ.get('ORCHESTRATOR_BASE_URL', None)
session = requests.Session()
adapter = HTTPAdapter(pool_connections=1, pool_maxsize=10)
session.mount('http://', adapter)
session.mount('https://', adapter)
