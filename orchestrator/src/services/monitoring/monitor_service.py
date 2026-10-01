from src.monitors import monitor_registry
from src.persistence.MonitorStorage import MonitorStorage
from src.services.monitoring.monitor_runtime import MonitorDispatcher, MonitorRunner


def list_monitors():
    with MonitorStorage() as storage:
        for item in monitor_registry.list(): storage.ensure_monitor(item)
        states={item['key']:item for item in storage.list_states()}
    return [{**item.to_dict(),'runtime':states.get(item.key,{})} for item in monitor_registry.list()]


def get_monitor(key):
    item=monitor_registry.get(key)
    if item is None:return None
    with MonitorStorage() as storage:
        storage.ensure_monitor(item);state=next((x for x in storage.list_states() if x['key']==key),{})
        return {**item.to_dict(),'runtime':state,'incidents':storage.list_incidents(key)}


def set_monitor_enabled(key,value):
    item=monitor_registry.get(key)
    if item is None:raise ValueError(f'Monitor not found: {key}')
    with MonitorStorage() as storage:storage.ensure_monitor(item);storage.set_enabled(key,value)


def run_monitor_now(key):
    result=MonitorRunner().poll(key);MonitorDispatcher().dispatch_pending();return result


def retry_incident(incident_id):
    with MonitorStorage() as storage: run_id=storage.prepare_incident_retry(incident_id)
    if run_id is None: raise ValueError('Incident is not retryable')
    MonitorDispatcher().dispatch_pending(limit=1)
    return str(run_id)
