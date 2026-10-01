from __future__ import annotations

import logging
import os
import uuid
from functools import partial

from apscheduler.executors.pool import ThreadPoolExecutor as APThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

from src.monitors import monitor_registry
from src.services.monitoring.monitor_runtime import MonitorDispatcher, MonitorRunner
from src.services.workflows.workflow_service import get_workflow

log=logging.getLogger(__name__)


class MonitorSchedulerService:
    _instance=None
    def __init__(self):
        self.scheduler=BackgroundScheduler(daemon=True,timezone=pytz.timezone('Europe/Oslo'),
            executors={'default':APThreadPoolExecutor(max_workers=max(1,int(os.getenv('MONITOR_WORKER_THREADS','4'))))})
    @classmethod
    def instance(cls):
        if cls._instance is None: cls._instance=cls()
        return cls._instance
    def start_all_monitors(self):
        self.scheduler.remove_all_jobs()
        for item in monitor_registry.list():
            if get_workflow(item.response_workflow) is None: raise ValueError(f"Monitor {item.key} references unknown workflow {item.response_workflow}")
            self.scheduler.add_job(partial(self._run,item.key),'interval',seconds=item.interval_seconds,
                id=f'monitor:{item.key}',replace_existing=True,max_instances=1,coalesce=True)
        self.scheduler.add_job(self._dispatch,'interval',seconds=int(os.getenv('MONITOR_DISPATCH_INTERVAL_SECONDS','15')),
            id='monitor:dispatcher',replace_existing=True,max_instances=1,coalesce=True)
        if not self.scheduler.running:self.scheduler.start()
    def run_now(self,key):
        if monitor_registry.get(key) is None: raise ValueError(f"Monitor not found: {key}")
        self.scheduler.add_job(partial(self._run,key),'date',id=f'monitor:{key}:manual:{uuid.uuid4()}')
    @staticmethod
    def _run(key):
        try: MonitorRunner().poll(key);MonitorDispatcher().dispatch_pending()
        except Exception: log.exception('Monitor poll failed: %s',key)
    @staticmethod
    def _dispatch():
        try: MonitorDispatcher().dispatch_pending()
        except Exception: log.exception('Monitor dispatch failed')
