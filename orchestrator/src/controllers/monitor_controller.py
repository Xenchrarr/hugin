from flask import Blueprint, request

from src.auth import require_admin
from src.services.monitoring.monitor_service import get_monitor, list_monitors, retry_incident, run_monitor_now, set_monitor_enabled

monitor_blueprint=Blueprint('monitors',__name__)


@monitor_blueprint.route('/',methods=['GET'])
@monitor_blueprint.route('/list',methods=['GET'])
@require_admin
def monitors():return list_monitors()


@monitor_blueprint.route('/<key>',methods=['GET'])
@require_admin
def detail(key):
    value=get_monitor(key);return (value,200) if value else ({'message':'Monitor not found'},404)


@monitor_blueprint.route('/<key>/enabled',methods=['PUT'])
@require_admin
def enabled(key):
    body=request.get_json(silent=True) or {};value=body.get('enabled')
    if value is not None and not isinstance(value,bool):return {'message':'enabled must be boolean or null'},400
    try:set_monitor_enabled(key,value);return {'message':'Monitor override updated'},200
    except ValueError as exc:return {'message':str(exc)},404


@monitor_blueprint.route('/<key>/run',methods=['POST'])
@require_admin
def run(key):
    try:return run_monitor_now(key),200
    except ValueError as exc:return {'message':str(exc)},404


@monitor_blueprint.route('/incidents/<incident_id>/retry',methods=['POST'])
@require_admin
def retry(incident_id):
    try:return {'message':'Incident response queued','job_run_id':retry_incident(incident_id)},202
    except ValueError as exc:return {'message':str(exc)},409
