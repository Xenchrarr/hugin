-- GUI-authored workflow catalog. Step implementations remain code-defined;
-- published workflow revisions are immutable data and executions snapshot them.

CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY,
    key VARCHAR(120) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active_revision_id UUID,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    lock_version INTEGER NOT NULL DEFAULT 1 CHECK (lock_version > 0),
    created_by VARCHAR(255) NOT NULL,
    updated_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_revisions (
    id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    version INTEGER,
    state VARCHAR(20) NOT NULL CHECK (state IN ('draft', 'published')),
    editor_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    compiled_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by VARCHAR(255) NOT NULL,
    published_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    CHECK ((state = 'draft' AND version IS NULL AND published_at IS NULL)
        OR (state = 'published' AND version IS NOT NULL AND version > 0 AND published_at IS NOT NULL)),
    UNIQUE (workflow_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS workflow_revisions_one_draft_idx
    ON workflow_revisions(workflow_id) WHERE state = 'draft';
CREATE INDEX IF NOT EXISTS workflow_revisions_history_idx
    ON workflow_revisions(workflow_id, version DESC) WHERE state = 'published';

CREATE OR REPLACE FUNCTION protect_published_workflow_revision() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.state = 'published' THEN
        RAISE EXCEPTION 'Published workflow revisions are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'workflow_revisions_immutable') THEN
        CREATE TRIGGER workflow_revisions_immutable
            BEFORE UPDATE OR DELETE ON workflow_revisions
            FOR EACH ROW EXECUTE FUNCTION protect_published_workflow_revision();
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'workflows_active_revision_fk') THEN
        ALTER TABLE workflows ADD CONSTRAINT workflows_active_revision_fk
            FOREIGN KEY (active_revision_id) REFERENCES workflow_revisions(id);
    END IF;
END $$;

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS workflow_revision_id UUID;
ALTER TABLE workflow_step_runs ADD COLUMN IF NOT EXISTS step_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE monitor_incidents ADD COLUMN IF NOT EXISTS workflow_revision_id UUID;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'jobs_workflow_revision_fk') THEN
        ALTER TABLE jobs ADD CONSTRAINT jobs_workflow_revision_fk
            FOREIGN KEY (workflow_revision_id) REFERENCES workflow_revisions(id);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'monitor_incidents_workflow_revision_fk') THEN
        ALTER TABLE monitor_incidents ADD CONSTRAINT monitor_incidents_workflow_revision_fk
            FOREIGN KEY (workflow_revision_id) REFERENCES workflow_revisions(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS jobs_workflow_revision_idx ON jobs(workflow_revision_id);
CREATE INDEX IF NOT EXISTS monitor_incidents_workflow_revision_idx
    ON monitor_incidents(workflow_revision_id);
