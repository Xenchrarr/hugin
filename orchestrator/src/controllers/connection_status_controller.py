import logging

from flask import Blueprint, make_response, request

from src.api.powershell_runner.health_check import check_if_powershell_script_engine_is_up
from src.services.connection_status_service import check_if_connection_to_job_db_is_valid

log = logging.getLogger(__name__)

connection_status_blueprint = Blueprint('connection_status', __name__)

status_items = ['database', "script_runner"]
status_items_simple = ['database',]

@connection_status_blueprint.route('/status', methods=['GET'])
def get_connection_status()-> dict:
    try:
        status_item = request.args.get('status_item')
        # print(f"status_item: {status_item}")
        string_response = get_string_response(status_item)
        log.debug("%s: %s", status_item, string_response)
        return string_response
    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'Error': str(e),
        }


@connection_status_blueprint.route('/status_items', methods=['GET'])
def get_status_items():
    try:
        return status_items

    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'Error': str(e),
        }, 500

@connection_status_blueprint.route('/status_items_simple', methods=['GET'])
def get_status_items_simple():
    try:
        return status_items_simple

    except Exception as e:
        return {
            'message': f"Something went wrong {e}",
            'status': 500,
            'Error': str(e),
        }, 500



def get_string_response(status_item) -> dict:

    try:
        if status_item == 'orchestrator':
            result = True
        elif status_item == 'database':
            result = check_if_connection_to_job_db_is_valid()
        elif status_item == 'script_runner':
            result = check_if_powershell_script_engine_is_up()
        else:
            log.warning("Unknown status item %s", status_item)
            result = False
    except Exception as e:
        result = False

    return {"status": result}

@connection_status_blueprint.route('/health', methods=['GET'])
def health_check():
    return {"status": "alive"}, 200