import traceback

from flask import Blueprint, request

from src.services import get_git_sync_service, refresh_git_sync_service
from src.services.log_service import log_info, log_error

git_blueprint = Blueprint('git', __name__)


@git_blueprint.route('/sync', methods=['POST'])
def sync():
    try:
        service = get_git_sync_service()
        if service is None:
            return {'message': 'Git sync not configured (no repos available)', 'status': 400}, 400

        body = request.get_json(silent=True) or {}
        repo_name = body.get('repo_name')

        log_info(f"Git sync requested" + (f" for repo '{repo_name}'" if repo_name else " for all repos"))
        result = service.sync(repo_name=repo_name)
        return {'message': 'Sync complete', 'status': 200, 'result': result}, 200

    except ValueError as e:
        return {'message': str(e), 'status': 400}, 400
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        log_error(f"Git sync failed: {e}", stack_trace=stack_trace)
        return {'message': f'Git sync failed: {e}', 'status': 500}, 500


@git_blueprint.route('/status', methods=['GET'])
def status():
    try:
        service = get_git_sync_service()
        if service is None:
            return {'message': 'Git sync not configured (no repos available)', 'status': 400}, 400

        repo_name = request.args.get('repo_name')
        result = service.status(repo_name=repo_name)
        return {'message': 'OK', 'status': 200, 'result': result}, 200

    except ValueError as e:
        return {'message': str(e), 'status': 400}, 400
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        log_error(f"Git status check failed: {e}", stack_trace=stack_trace)
        return {'message': f'Git status check failed: {e}', 'status': 500}, 500


@git_blueprint.route('/refresh', methods=['POST'])
def refresh():
    try:
        log_info("Refreshing git repos from orchestrator DB")
        service = refresh_git_sync_service()
        if service is None:
            return {'message': 'No repos available after refresh', 'status': 200, 'result': []}, 200

        return {
            'message': 'Repos refreshed',
            'status': 200,
            'result': service.repo_names,
        }, 200
    except Exception as e:
        stack_trace = ''.join(traceback.format_exception(e))
        log_error(f"Git refresh failed: {e}", stack_trace=stack_trace)
        return {'message': f'Git refresh failed: {e}', 'status': 500}, 500
