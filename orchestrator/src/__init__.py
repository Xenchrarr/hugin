import logging
import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_cors import CORS

from .config.config import Config
from .routes import api
from src.services.core.job_scheduler_service import JobSchedulerService
from src.services.core.reminder_scheduler_service import ReminderSchedulerService
from src.persistence.JobDb import JobDb
from src.persistence.Database import run_init_sql, run_migrations



log = logging.getLogger(__name__)
config = Config().active

app = Flask(__name__)
_cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(",")
CORS(app, resources={r"/*": {"origins": _cors_origins}})

app.env = config.ENV

app.register_blueprint(api, url_prefix="/api")


@app.teardown_appcontext
def _return_db_connection(exc):
    """Return the thread-local DB connection to the pool after every request."""
    try:
        JobDb.instance().close_connection(commit=exc is None)
    except Exception:
        pass


job_service_running = os.environ.get("JOB_SCHEDULER_RUNNING", "False") == "True"

try:
    JobDb.instance()  # ensure the pool is initialized
    run_init_sql()
    run_migrations()
except Exception as exc:
    log.warning("Database init skipped: %s", exc)

try:
    if job_service_running:
        JobSchedulerService.instance().start_all_jobs()
        # Share the scheduler instance and load active reminders
        reminder_svc = ReminderSchedulerService.instance()
        reminder_svc.init_scheduler(JobSchedulerService.instance().scheduler)
        reminder_svc.load_active_reminders()
except Exception as exc:
    log.warning("Scheduler startup skipped: %s", exc)