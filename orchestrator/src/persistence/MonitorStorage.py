from __future__ import annotations

import json
import uuid

from src.monitors import IncidentCandidate, MonitorDefinition, Observation
from src.persistence.JobDb import JobDb


class MonitorStorage:
    def __init__(self): self.db = JobDb.instance()
    def __enter__(self): return self
    def __exit__(self, *_): self.release_connection()
    def release_connection(self): self.db.close_connection()

    def ensure_monitor(self, definition: MonitorDefinition):
        self.db.execute("""INSERT INTO monitor_runtime_state(monitor_key,definition_version,definition_enabled)
            VALUES(%s,%s,%s) ON CONFLICT(monitor_key) DO UPDATE SET definition_version=EXCLUDED.definition_version,
            definition_enabled=EXCLUDED.definition_enabled,updated_at=NOW()""",
            (definition.key, definition.version, definition.enabled)); self.db.commit()

    def try_acquire_poll_lease(self, key, owner, seconds):
        row=self.db.execute("""UPDATE monitor_runtime_state SET lease_owner=%s,
            lease_until=NOW()+make_interval(secs=>%s),last_poll_started_at=NOW(),updated_at=NOW()
            WHERE monitor_key=%s AND COALESCE(enabled_override,definition_enabled)=TRUE
            AND (lease_until IS NULL OR lease_until<NOW()) RETURNING monitor_key""",(owner,seconds,key)).fetchone();self.db.commit();return bool(row)

    def get_checkpoint(self,key):
        row=self.db.execute("SELECT checkpoint FROM monitor_runtime_state WHERE monitor_key=%s",(key,)).fetchone();return row[0] if row else {}

    def insert_observations(self,key,items):
        count=0
        for item in items:
            row=self.db.execute("""INSERT INTO monitor_observations(id,monitor_key,source_event_id,occurred_at,correlation_key,signals,attributes,evidence)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(monitor_key,source_event_id) DO NOTHING RETURNING id""",
              (uuid.uuid4(),key,item.source_event_id,item.occurred_at,item.correlation_key,json.dumps(sorted(item.signals)),json.dumps(item.attributes),json.dumps(item.evidence))).fetchone();count+=bool(row)
        self.db.commit();return count

    def get_observations_since(self,key,since):
        rows=self.db.execute("""SELECT source_event_id,occurred_at,signals,correlation_key,attributes,evidence
          FROM monitor_observations WHERE monitor_key=%s AND occurred_at>=%s ORDER BY occurred_at""",(key,since)).fetchall()
        return [Observation(r[0],r[1],frozenset(r[2]),r[3],r[4],r[5]) for r in rows]

    def delete_observations_before(self, key, cutoff):
        self.db.execute("DELETE FROM monitor_observations WHERE monitor_key=%s AND occurred_at<%s",
                        (key, cutoff)); self.db.commit()

    def claim_incident(self, definition, candidate: IncidentCandidate):
        incident_id, run_id = uuid.uuid4(), uuid.uuid4(); workflow=candidate.response_workflow or definition.response_workflow
        payload=candidate.workflow_input(incident_id)
        revision = self.db.execute("""SELECT active_revision_id FROM workflows
          WHERE key=%s AND archived=FALSE AND active_revision_id IS NOT NULL""", (workflow,)).fetchone()
        if not revision:
            raise ValueError(f"Published response workflow not found: {workflow}")
        row=self.db.execute("""INSERT INTO monitor_incidents(id,monitor_key,incident_type,dedupe_key,correlation_key,first_seen_at,last_seen_at,evidence,response_workflow_key,workflow_revision_id,workflow_run_id,workflow_input)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(monitor_key,dedupe_key) DO UPDATE SET last_seen_at=GREATEST(monitor_incidents.last_seen_at,EXCLUDED.last_seen_at),updated_at=NOW() RETURNING id,workflow_run_id,response_status,workflow_revision_id""",
          (incident_id,definition.key,candidate.incident_type,candidate.dedupe_key,candidate.correlation_key,candidate.first_seen_at,candidate.last_seen_at,json.dumps(payload["evidence"]),workflow,revision[0],run_id,json.dumps(payload))).fetchone();self.db.commit()
        return {"id":str(row[0]),"workflow_run_id":str(row[1]),"response_status":row[2],"workflow_revision_id":str(row[3]),"workflow_key":workflow,"workflow_input":payload} if row and row[0]==incident_id else None

    def finish_poll(self,key,owner,checkpoint,errors=()):
        self.db.execute("""UPDATE monitor_runtime_state SET checkpoint=%s,last_success_at=CASE WHEN %s='' THEN NOW() ELSE last_success_at END,
          last_error=%s,consecutive_failures=CASE WHEN %s='' THEN 0 ELSE consecutive_failures+1 END,lease_owner=NULL,lease_until=NULL,updated_at=NOW()
          WHERE monitor_key=%s AND lease_owner=%s""",(json.dumps(checkpoint),"; ".join(errors),"; ".join(errors),"; ".join(errors),key,owner));self.db.commit()

    def list_states(self):
        rows=self.db.execute("""SELECT monitor_key,definition_version,definition_enabled,enabled_override,
          COALESCE(enabled_override,definition_enabled),checkpoint,last_poll_started_at,last_success_at,last_error,
          consecutive_failures FROM monitor_runtime_state ORDER BY monitor_key""").fetchall()
        return [{"key":r[0],"definition_version":r[1],"definition_enabled":r[2],"enabled_override":r[3],
                 "enabled":r[4],"checkpoint":r[5],"last_poll_started_at":r[6],"last_success_at":r[7],
                 "last_error":r[8],"consecutive_failures":r[9]} for r in rows]

    def list_incidents(self,key):
        rows=self.db.execute("""SELECT id,incident_type,dedupe_key,correlation_key,first_seen_at,last_seen_at,
          evidence,response_workflow_key,response_status,workflow_run_id,last_error,workflow_revision_id FROM monitor_incidents
          WHERE monitor_key=%s ORDER BY created_at DESC LIMIT 200""",(key,)).fetchall()
        return [{"id":str(r[0]),"incident_type":r[1],"dedupe_key":r[2],"correlation_key":r[3],
                 "first_seen_at":r[4],"last_seen_at":r[5],"evidence":r[6],"response_workflow":r[7],
                 "response_status":r[8],"workflow_run_id":str(r[9]),"last_error":r[10],
                 "workflow_revision_id":str(r[11])} for r in rows]

    def set_enabled(self,key,value):
        self.db.execute("UPDATE monitor_runtime_state SET enabled_override=%s,updated_at=NOW() WHERE monitor_key=%s",(value,key));self.db.commit()

    def claim_pending_incident(self, owner, lease_seconds=300):
        row=self.db.execute("""WITH candidate AS (SELECT id FROM monitor_incidents
          WHERE response_status IN ('Pending','Dispatching') AND (dispatch_lease_until IS NULL OR dispatch_lease_until<NOW())
          ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
          UPDATE monitor_incidents i SET response_status='Dispatching',dispatch_lease_owner=%s,
          dispatch_lease_until=NOW()+make_interval(secs=>%s),updated_at=NOW() FROM candidate c WHERE i.id=c.id
        RETURNING i.id,i.response_workflow_key,i.workflow_revision_id,i.workflow_run_id,i.workflow_input""",(owner,lease_seconds)).fetchone();self.db.commit();return row

    def reconcile_finished_responses(self):
        self.db.execute("""UPDATE monitor_incidents i SET response_status=r.status,
          last_error=CASE WHEN r.status='Error' THEN r.result ELSE '' END,
          dispatch_lease_owner=NULL,dispatch_lease_until=NULL,updated_at=NOW()
          FROM job_runs r WHERE r.id=i.workflow_run_id AND i.response_status IN ('Running','Dispatching')
          AND r.status IN ('Finished','Partial','Nothing','Error','Cancelled')""");self.db.commit()

    def register_incident_run(self, incident_id, run_id):
        self.db.execute("""INSERT INTO monitor_incident_runs(incident_id,job_run_id,attempt)
          SELECT %s,%s,COALESCE(MAX(attempt),0)+1 FROM monitor_incident_runs WHERE incident_id=%s
          ON CONFLICT DO NOTHING""",(incident_id,run_id,incident_id));self.db.commit()

    def prepare_incident_retry(self, incident_id):
        run_id=uuid.uuid4()
        row=self.db.execute("""UPDATE monitor_incidents SET workflow_run_id=%s,response_status='Pending',
          dispatch_lease_owner=NULL,dispatch_lease_until=NULL,last_error='',updated_at=NOW()
          WHERE id=%s AND response_status IN ('Error','Cancelled','Partial') RETURNING workflow_run_id""",
          (run_id,incident_id)).fetchone();self.db.commit();return row[0] if row else None

    def mark_dispatched(self,incident_id,status,error=''):
        self.db.execute("UPDATE monitor_incidents SET response_status=%s,last_error=%s,dispatch_attempts=dispatch_attempts+1,updated_at=NOW() WHERE id=%s",(status,error,incident_id));self.db.commit()
