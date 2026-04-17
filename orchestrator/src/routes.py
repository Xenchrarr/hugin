from flask import Blueprint

from src.controllers.job_log_controller import job_log_blueprint
from src.controllers.jobs_controller import jobs_blueprint
from src.controllers.logger_controller import logger_blueprint

from src.controllers.job_run_controller import job_run_blueprint
from src.controllers.connection_status_controller import connection_status_blueprint
from src.controllers.git_repo_controller import git_repo_blueprint
from src.controllers.scripts_controller import scripts_blueprint
from src.controllers.script_permission_controller import script_permission_blueprint
from src.controllers.script_reason_controller import script_reason_blueprint
from src.controllers.dashboard_controller import dashboard_blueprint
from src.controllers.reminder_controller import reminder_blueprint

api = Blueprint('api', __name__)


api.register_blueprint(jobs_blueprint, url_prefix="/jobs")
api.register_blueprint(job_run_blueprint, url_prefix="/jobrun")
api.register_blueprint(job_log_blueprint, url_prefix="/joblog")

api.register_blueprint(connection_status_blueprint, url_prefix="/connection_status")


api.register_blueprint(logger_blueprint, url_prefix="/logger")

api.register_blueprint(git_repo_blueprint, url_prefix="/git_repos")

api.register_blueprint(scripts_blueprint, url_prefix="/scripts")

api.register_blueprint(script_permission_blueprint, url_prefix="/script_permissions")

api.register_blueprint(script_reason_blueprint, url_prefix="/script_reasons")

api.register_blueprint(dashboard_blueprint, url_prefix="/dashboard")

api.register_blueprint(reminder_blueprint, url_prefix="/reminders")