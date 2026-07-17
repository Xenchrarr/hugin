import os

import requests
from requests.adapters import HTTPAdapter

ORCHESTRATOR_API_URL = os.environ.get('ORCHESTRATOR_API_URL', None)
session = requests.Session()
adapter = HTTPAdapter(pool_connections=1, pool_maxsize=10)
session.mount('http://', adapter)
session.mount('https://', adapter)
