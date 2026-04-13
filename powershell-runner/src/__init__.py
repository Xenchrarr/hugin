import json
import os

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())
# app.env = config.ENV

from .routes import api

app.register_blueprint(api, url_prefix="/api")

import logging

_log = logging.getLogger(__name__)

# Auto-clone scripts repos on startup if configured
try:
    from src.services import get_git_sync_service
    _git_svc = get_git_sync_service()
    if _git_svc:
        _git_svc.ensure_cloned()
except Exception as _e:
    _log.warning("Git clone skipped: %s", _e)

