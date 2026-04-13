import os

import requests

TEAMS_WEBHOOK_URL = os.environ.get('TEAMS_WEBHOOK_URL', None)
bot_enabled = False

if TEAMS_WEBHOOK_URL is not None:
    bot_enabled = True



