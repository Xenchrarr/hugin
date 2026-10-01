
import threading
import traceback

from flask import Blueprint, request

from src.ThreadLocalSingleton import ThreadLocalSingleton
from src.services.log_service import flush_all, log_info, log_error
from src.services.script_runner_service import ScriptRunnerService
from src.services.script_listing_service import ScriptListingService
from src.api.orchestrator.callback import post_result

script_blueprint = Blueprint('script', __name__)


def _run_background(runner):
    local = ThreadLocalSingleton.instance().thread_local
    local.job_run_id = runner.job_run_id
    local.step_run_id = runner.step_run_id
    try:
        result = runner.run()
        status = 'Finished' if result.get('completed') else 'Error'
        message = (f"Script '{runner.script_name}' finished" if status == 'Finished'
                   else f"Script '{runner.script_name}' failed")
    except Exception as exc:
        result, status, message = {'completed': False, 'error': str(exc)}, 'Error', str(exc)
        log_error(message, traceback.format_exc(), job_run_id=runner.job_run_id,
                  step_run_id=runner.step_run_id)
    flush_all()
    try:
        post_result(runner.job_run_id, status, result, message, runner.step_run_id)
    except Exception:
        traceback.print_exc()


@script_blueprint.route('/list', methods=['GET'])
def list_scripts():
    """List available scripts and their parameters for a given folder."""
    folder = request.args.get('folder', '')
    if not folder:
        return {'message': 'folder query parameter is required', 'status': 400}, 400

    try:
        service = ScriptListingService()
        scripts = service.list_scripts(folder)
        return {'scripts': scripts, 'status': 200}, 200
    except FileNotFoundError as e:
        return {'message': str(e), 'status': 404}, 404
    except ValueError as e:
        return {'message': str(e), 'status': 400}, 400


@script_blueprint.route('/run', methods=['POST'])
def run_script():
    """
    Run a .ps1 script.

    Expected JSON body:
        {
            "job_run_id": 123,
            "script_name": "myscript.ps1",
            "stop_words": ["error", "fatal"]   # optional
        }
    """
    try:
        body = request.get_json(force=True)
        job_run_id = body.get('job_run_id')
        step_run_id = body.get('step_run_id')
        script_name = body.get('script_name')
        stop_words = body.get('stop_words', [])
        params = body.get('params', {})

        if not job_run_id or not script_name:
            return {'message': 'job_run_id and script_name are required', 'status': 400}, 400

        thread_local = ThreadLocalSingleton.instance().thread_local
        thread_local.job_run_id = job_run_id
        thread_local.step_run_id = step_run_id

        log_info(f"Will attach logs to job_run_id: {job_run_id}")

        runner = ScriptRunnerService(
            job_run_id=job_run_id,
            script_name=script_name,
            stop_words=stop_words,
            params=params,
            step_run_id=step_run_id,
        )

        threading.Thread(
            target=_run_background,
            args=(runner,),
            daemon=True,
            name=f'powershell-{step_run_id or job_run_id}',
        ).start()
        return {
            'message': 'Script accepted',
            'status': 202,
            'job_run_id': str(job_run_id),
            'step_run_id': str(step_run_id) if step_run_id else None,
        }, 202

    except FileNotFoundError as e:
        return {'message': str(e), 'status': 404}, 404
    except ValueError as e:
        return {'message': str(e), 'status': 400}, 400
    except Exception as e:
        thread_local = ThreadLocalSingleton.instance().thread_local
        job_run_id = getattr(thread_local, 'job_run_id', None)
        stack_trace = traceback.format_exception(e)
        stack_trace_string = '\n'.join(stack_trace)
        log_error(
            f"Something went wrong {e}",
            stack_trace_string,
            job_run_id=job_run_id)
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'Error': str(e),
        }, 500
