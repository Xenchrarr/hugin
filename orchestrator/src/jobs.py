import json
import os

from src.persistence.DatabaseLogger import DatabaseLogger

from src.services.external.powershell_service import run_test_script, run_script
from src.services.external.git_service import run_git_sync
from src.services.external.power_aggregation_service import run_power_aggregation
from src.services.external.printer_hub_service import run_print_news

from src.jobs_registry import job_type

# Load job descriptions from the external JSON file
def load_job_descriptions():

    descriptions_path = os.path.join(os.path.dirname(__file__), "job_descriptions.json")
    with open(descriptions_path, "r") as file:
        return json.load(file)

JOB_DESCRIPTIONS = load_job_descriptions()


_ENABLE_TEST_JOBS = os.environ.get('ENABLE_TEST_JOBS', 'false').lower() == 'true'

if _ENABLE_TEST_JOBS:
    @job_type('test', 'Dette er en tesssst')
    def one_test_job_function(param: str = '0'):
        logger = DatabaseLogger()
        logger.log_info("Nå logger vi...")

    @job_type('test_large_log', 'Test that large log messages are saved to file storage and shown as download links')
    def test_large_log_job(param: str = '0'):
        logger = DatabaseLogger()
        logger.log_info("Starting large log test...")
        large_message = "LARGE LOG TEST | " + ("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 " * 50)
        logger.log_info(f"Logging a message with {len(large_message)} characters (threshold is 2000)...")
        logger.log_info(large_message)
        logger.log_error("Large error stack trace test", stack_trace="STACK TRACE | " + ("Error detail line. " * 200))
        logger.log_info("Small message - this should appear as normal text.")
        logger.log_info("Large log test completed. Check that the large entries above are download links.")

    @job_type('powershell_script', 'Run a test PowerShell script')
    def test_powershell(param: str = ""):
        run_test_script()


@job_type('run_script', JOB_DESCRIPTIONS.get('run_script', 'Run a PowerShell script with parameters'))
def run_script_job(param: str = ""):
    if not param:
        raise Exception("Missing parameter JSON (script_name required)")

    import json as _json
    params = _json.loads(param)
    script_name = params.pop('script_name', None)
    if not script_name:
        raise Exception("script_name is required in parameter JSON")

    run_script(script_name, params)


@job_type('git_sync', JOB_DESCRIPTIONS.get('git_sync', 'Sync a git repository'))
def git_sync_job(param: str = ""):
    run_git_sync(param)


@job_type('power_aggregation', JOB_DESCRIPTIONS.get('power_aggregation', 'Trigger hugin-core daily energy aggregation'))
def power_aggregation_job(param: str = ""):
    run_power_aggregation(param)


@job_type('print_news', JOB_DESCRIPTIONS.get('print_news', 'Fetch news headlines from an RSS feed and print them'))
def print_news_job(param: str = ""):
    run_print_news(param)

