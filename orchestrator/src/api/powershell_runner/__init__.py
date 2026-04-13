import os

import requests

from src.api.RestCredentialMissingError import RestCredentialMissingError

POWERSHELL_API_ENDPOINT = os.environ.get("POWERSHELL_API_ENDPOINT", None)

if POWERSHELL_API_ENDPOINT is None:
    raise RestCredentialMissingError("Missing POWERSHELL_API_ENDPOINT environment variable")

# Timeout (seconds) for HTTP calls to the powershell-runner service.
# Scripts can be long-running, so the default is generous (15 min).
POWERSHELL_SCRIPT_TIMEOUT = int(os.environ.get("POWERSHELL_SCRIPT_TIMEOUT", "900"))
POWERSHELL_LIST_TIMEOUT = int(os.environ.get("POWERSHELL_LIST_TIMEOUT", "30"))

session = requests.Session()