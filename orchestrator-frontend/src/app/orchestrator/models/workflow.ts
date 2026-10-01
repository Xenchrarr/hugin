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
    inputs: Record<string, unknown>;
    run_if?: Record<string, unknown>;
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
    description: string;
    input_schema: JsonSchema;
    output_schema: JsonSchema;
    idempotent: boolean;
}

export interface WorkflowStepRun {
    id: string;
    step_key: string;
    step_type: string;
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
