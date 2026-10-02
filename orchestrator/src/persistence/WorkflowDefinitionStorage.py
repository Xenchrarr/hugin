from __future__ import annotations

import copy
import json
import uuid

from src.models.orchestrator.WorkflowRevision import WorkflowRevision
from src.persistence.JobDb import JobDb


class WorkflowConflictError(ValueError):
    pass


class WorkflowDefinitionStorage:
    _SELECT = """
        SELECT r.id,r.workflow_id,w.key,w.name,w.description,r.version,r.state,
               r.editor_definition,r.compiled_definition,w.lock_version,w.archived,
               r.created_at,r.published_at
        FROM workflow_revisions r JOIN workflows w ON w.id=r.workflow_id
    """

    def __init__(self, db=None):
        self.db = db or JobDb.instance()

    @staticmethod
    def _model(row) -> WorkflowRevision | None:
        if not row:
            return None
        return WorkflowRevision(
            id=str(row[0]), workflow_id=str(row[1]), key=row[2], name=row[3],
            description=row[4], version=row[5], state=row[6],
            editor_definition=row[7] or {}, compiled_definition=row[8] or {},
            lock_version=row[9], archived=row[10], created_at=row[11], published_at=row[12],
        )

    def list_published(self) -> list[WorkflowRevision]:
        rows = self.db.execute(self._SELECT + """
            WHERE w.active_revision_id=r.id AND w.archived=FALSE ORDER BY w.key
        """).fetchall()
        return [self._model(row) for row in rows]

    def list_all_published(self) -> list[WorkflowRevision]:
        rows = self.db.execute(self._SELECT + """
            WHERE r.state='published' ORDER BY w.key,r.version DESC
        """).fetchall()
        return [self._model(row) for row in rows]

    def list_catalog(self) -> list[dict]:
        rows = self.db.execute("""SELECT w.key,w.name,w.description,w.archived,w.lock_version,
            published.id,published.version,draft.id,w.updated_at
            FROM workflows w
            LEFT JOIN workflow_revisions published ON published.id=w.active_revision_id
            LEFT JOIN workflow_revisions draft ON draft.workflow_id=w.id AND draft.state='draft'
            ORDER BY w.archived,w.key""").fetchall()
        return [{
            "key": row[0], "name": row[1], "description": row[2], "archived": row[3],
            "lock_version": row[4], "active_revision_id": str(row[5]) if row[5] else None,
            "active_version": row[6], "draft_revision_id": str(row[7]) if row[7] else None,
            "updated_at": row[8].isoformat() if hasattr(row[8], "isoformat") else row[8],
        } for row in rows]

    def get_published(self, key: str, version: int | None = None) -> WorkflowRevision | None:
        if version is None:
            row = self.db.execute(self._SELECT + """
                WHERE w.key=%s AND w.active_revision_id=r.id AND w.archived=FALSE
            """, (key,)).fetchone()
        else:
            row = self.db.execute(self._SELECT + """
                WHERE w.key=%s AND r.version=%s AND r.state='published'
            """, (key, version)).fetchone()
        return self._model(row)

    def get_revision(self, revision_id: str) -> WorkflowRevision | None:
        row = self.db.execute(self._SELECT + " WHERE r.id=%s AND r.state='published'",
                              (revision_id,)).fetchone()
        return self._model(row)

    def get_draft(self, key: str) -> WorkflowRevision | None:
        row = self.db.execute(self._SELECT + " WHERE w.key=%s AND r.state='draft'", (key,)).fetchone()
        return self._model(row)

    def list_revisions(self, key: str) -> list[WorkflowRevision]:
        rows = self.db.execute(self._SELECT + """
            WHERE w.key=%s AND r.state='published' ORDER BY r.version DESC
        """, (key,)).fetchall()
        return [self._model(row) for row in rows]

    def clone_revision(self, key: str, version: int, expected_lock: int,
                       user: str) -> WorkflowRevision:
        try:
            workflow = self.db.execute(
                "SELECT id,lock_version FROM workflows WHERE key=%s AND archived=FALSE FOR UPDATE",
                (key,)).fetchone()
            if not workflow:
                raise ValueError(f"Workflow not found: {key}")
            if workflow[1] != expected_lock:
                raise WorkflowConflictError("Workflow was changed by another editor; reload before cloning")
            source = self.db.execute("""SELECT editor_definition FROM workflow_revisions
                WHERE workflow_id=%s AND version=%s AND state='published'""",
                (workflow[0], version)).fetchone()
            if not source:
                raise ValueError(f"Published workflow revision not found: {key}@{version}")
            draft = self.db.execute("""SELECT id FROM workflow_revisions
                WHERE workflow_id=%s AND state='draft' FOR UPDATE""", (workflow[0],)).fetchone()
            if draft:
                self.db.execute("UPDATE workflow_revisions SET editor_definition=%s,created_by=%s,created_at=NOW() WHERE id=%s",
                                (json.dumps(source[0]), user, draft[0]))
            else:
                self.db.execute("""INSERT INTO workflow_revisions
                    (id,workflow_id,state,editor_definition,created_by)
                    VALUES(%s,%s,'draft',%s,%s)""",
                    (uuid.uuid4(), workflow[0], json.dumps(source[0]), user))
            self.db.execute("""UPDATE workflows SET updated_by=%s,updated_at=NOW(),
                lock_version=lock_version+1 WHERE id=%s""", (user, workflow[0]))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_draft(key)

    def create(self, key: str, name: str, description: str, editor: dict, user: str) -> WorkflowRevision:
        workflow_id, revision_id = uuid.uuid4(), uuid.uuid4()
        try:
            self.db.execute("""INSERT INTO workflows
                (id,key,name,description,created_by,updated_by) VALUES(%s,%s,%s,%s,%s,%s)""",
                (workflow_id, key, name, description, user, user))
            self.db.execute("""INSERT INTO workflow_revisions
                (id,workflow_id,state,editor_definition,created_by) VALUES(%s,%s,'draft',%s,%s)""",
                (revision_id, workflow_id, json.dumps(editor), user))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_draft(key)

    def ensure_draft(self, key: str, user: str) -> WorkflowRevision | None:
        draft = self.get_draft(key)
        if draft:
            return draft
        active = self.get_published(key)
        if not active:
            return None
        revision_id = uuid.uuid4()
        editor = active.editor_definition or self._editor_from_compiled(active.compiled_definition)
        try:
            self.db.execute("""INSERT INTO workflow_revisions
                (id,workflow_id,state,editor_definition,created_by) VALUES(%s,%s,'draft',%s,%s)
                ON CONFLICT DO NOTHING""",
                (revision_id, active.workflow_id, json.dumps(editor), user))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_draft(key)

    def save_draft(self, key: str, editor: dict, name: str, description: str,
                   expected_lock: int, user: str) -> WorkflowRevision:
        try:
            row = self.db.execute("SELECT id,lock_version FROM workflows WHERE key=%s FOR UPDATE", (key,)).fetchone()
            if not row:
                raise ValueError(f"Workflow not found: {key}")
            if row[1] != expected_lock:
                raise WorkflowConflictError("Workflow was changed by another editor; reload before saving")
            draft = self.db.execute("SELECT id FROM workflow_revisions WHERE workflow_id=%s AND state='draft'", (row[0],)).fetchone()
            if not draft:
                raise ValueError("Workflow draft not found")
            self.db.execute("UPDATE workflow_revisions SET editor_definition=%s WHERE id=%s",
                            (json.dumps(editor), draft[0]))
            self.db.execute("""UPDATE workflows SET name=%s,description=%s,updated_by=%s,
                updated_at=NOW(),lock_version=lock_version+1 WHERE id=%s""",
                (name, description, user, row[0]))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_draft(key)

    def publish(self, key: str, name: str, description: str, editor: dict,
                compiled: dict, expected_lock: int, user: str) -> WorkflowRevision:
        try:
            workflow = self.db.execute(
                "SELECT id,lock_version FROM workflows WHERE key=%s AND archived=FALSE FOR UPDATE", (key,)).fetchone()
            if not workflow:
                raise ValueError(f"Workflow not found: {key}")
            if workflow[1] != expected_lock:
                raise WorkflowConflictError("Workflow was changed by another editor; reload before publishing")
            draft = self.db.execute(
                "SELECT id FROM workflow_revisions WHERE workflow_id=%s AND state='draft' FOR UPDATE",
                (workflow[0],)).fetchone()
            if not draft:
                raise ValueError("Workflow draft not found")
            version_row = self.db.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM workflow_revisions WHERE workflow_id=%s",
                (workflow[0],)).fetchone()
            version = version_row[0]
            compiled = copy.deepcopy(compiled)
            compiled["version"] = version
            self.db.execute("""UPDATE workflow_revisions SET version=%s,state='published',
                editor_definition=%s,compiled_definition=%s,published_by=%s,published_at=NOW()
                WHERE id=%s""", (version, json.dumps(editor), json.dumps(compiled), user, draft[0]))
            self.db.execute("""UPDATE workflows SET active_revision_id=%s,name=%s,description=%s,
                updated_by=%s,updated_at=NOW(),lock_version=lock_version+1 WHERE id=%s""",
                (draft[0], name, description, user, workflow[0]))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get_published(key, version)

    def delete_draft(self, key: str, expected_lock: int, user: str) -> None:
        try:
            row = self.db.execute("SELECT id,lock_version,active_revision_id FROM workflows WHERE key=%s FOR UPDATE", (key,)).fetchone()
            if not row:
                raise ValueError(f"Workflow not found: {key}")
            if row[1] != expected_lock:
                raise WorkflowConflictError("Workflow was changed by another editor")
            self.db.execute("DELETE FROM workflow_revisions WHERE workflow_id=%s AND state='draft'", (row[0],))
            if row[2] is None:
                self.db.execute("DELETE FROM workflows WHERE id=%s", (row[0],))
            else:
                self.db.execute("UPDATE workflows SET updated_by=%s,updated_at=NOW(),lock_version=lock_version+1 WHERE id=%s", (user, row[0]))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def archive(self, key: str, user: str) -> None:
        self.db.execute("""UPDATE workflows SET archived=TRUE,updated_by=%s,updated_at=NOW(),
            lock_version=lock_version+1 WHERE key=%s""", (user, key))
        self.db.commit()

    @staticmethod
    def _editor_from_compiled(compiled: dict) -> dict:
        # Published GUI revisions normally retain their editor definition. This
        # fallback intentionally preserves literals while translating refs.
        return copy.deepcopy(compiled)
