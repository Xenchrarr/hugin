export interface JsonSchema {
    type?: string | string[];
    title?: string;
    description?: string;
    default?: unknown;
    enum?: unknown[];
    required?: string[];
    properties?: Record<string, JsonSchema>;
    items?: JsonSchema;
    additionalProperties?: boolean | JsonSchema;
    [key: string]: unknown;
}

export interface WorkflowStep {
    key: string;
    step: string;
    step_version: number;
    inputs: Record<string, unknown>;
    when?: WorkflowCondition;
    on_failure: 'stop' | 'continue';
}

export interface WorkflowDefinition {
    key: string;
    version: number;
    description: string;
    input_schema: JsonSchema;
    steps: WorkflowStep[];
}

export interface WorkflowStepType {
    key: string;
    version: number;
    description: string;
    input_schema: JsonSchema;
    output_schema: JsonSchema;
    idempotent: boolean;
}

export type WorkflowBinding =
    | {source: 'literal'; value: unknown}
    | {source: 'workflow_input'; path: (string | number)[]; optional?: boolean}
    | {source: 'step_output'; step_key: string; path: (string | number)[]; optional?: boolean}
    | {source: 'first_available'; candidates: WorkflowBinding[]};

export type WorkflowOperand =
    | {source: 'literal'; value: unknown}
    | {source: 'workflow_input'; path: (string | number)[]}
    | {source: 'step_output'; step_key: string; path: (string | number)[]};

export interface WorkflowCondition {
    op: 'eq' | 'ne' | 'exists' | 'is_true' | 'is_false' | 'all' | 'any' | 'not';
    left?: WorkflowOperand;
    right?: WorkflowOperand;
    value?: WorkflowOperand;
    conditions?: WorkflowCondition[];
    condition?: WorkflowCondition;
}

export interface WorkflowEditorStep {
    key: string;
    step: string;
    step_version: number;
    bindings: Record<string, WorkflowBinding>;
    when?: WorkflowCondition;
    on_failure: 'stop' | 'continue';
}

export interface WorkflowEditorDefinition {
    key: string;
    description: string;
    input_schema: JsonSchema;
    steps: WorkflowEditorStep[];
}

export interface WorkflowDraft extends WorkflowDefinition {
    revision_id: string;
    name: string;
    state: 'draft' | 'published';
    lock_version: number;
    archived: boolean;
    editor_definition: WorkflowEditorDefinition;
    created_at?: string;
    published_at?: string;
}

export interface WorkflowCatalogItem {
    key: string;
    name: string;
    description: string;
    archived: boolean;
    lock_version: number;
    active_revision_id?: string;
    active_version?: number;
    draft_revision_id?: string;
    updated_at?: string;
}

export interface WorkflowIssue {
    code: string;
    path: (string | number)[];
    message: string;
}

export interface WorkflowStepRun {
    id: string;
    step_key: string;
    step_type: string;
    step_version: number;
    attempt: number;
    status: string;
    resolved_input: Record<string, unknown>;
    output: Record<string, unknown>;
    error: Record<string, unknown>;
    summary: string;
    started_at?: string;
    completed_at?: string;
}

export interface WorkflowRunDetail {
    run: {
        id: string;
        name: string;
        status: string;
        result: string;
        job_type: string;
        workflow_version?: number;
        workflow_input?: Record<string, unknown>;
        [key: string]: unknown;
    };
    steps: WorkflowStepRun[];
    artifacts: {original_filename: string; download_url: string; step_run_id?: string}[];
}
