import os

import requests

POWERSHELL_API_ENDPOINT = os.environ.get(
    "POWERSHELL_API_ENDPOINT", "http://powershell-runner:6001/api")

# Timeout (seconds) for HTTP calls to the powershell-runner service.
# Scripts can be long-running, so the default is generous (15 min).
POWERSHELL_SCRIPT_TIMEOUT = int(os.environ.get("POWERSHELL_SCRIPT_TIMEOUT", "900"))
POWERSHELL_LIST_TIMEOUT = int(os.environ.get("POWERSHELL_LIST_TIMEOUT", "30"))

session = requests.Session()
