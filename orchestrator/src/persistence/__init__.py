import os

from flask.cli import load_dotenv

load_dotenv()

JOB_DB_HOST = os.environ.get('JOB_DB_HOST')

JOB_DB_USER_NAME = os.environ.get('JOB_DB_USER_NAME')
JOB_DB_PASSWORD = os.environ.get('JOB_DB_PASSWORD')
JOB_DB_CONNECTION_STRING = os.environ.get('JOB_DB_CONNECTION_STRING')
JOB_DB_PORT = os.environ.get("JOB_DB_PORT", "5432")
JOB_DB = os.environ.get("JOB_DB", "orchestrator")



