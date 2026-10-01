export class JobRun {
    // ID, NAME, START_TIME, END_TIME, STATUS, JOB_TYPE, RESULT, JOB_ID

    id: number = 0;
    name: string = '';
    start_time: string = '';
    end_time: string = '';
    status: string = '';
    job_type: string = '';
    result: string = '';
    job_id: number = 0;
    parameter: string = '';
    run_by: string = '';
    run_by_group: string = '';
    metadata: Record<string, any> = {};
    workflow_version: number|null = null;
    workflow_input: Record<string, unknown> = {};
    last_activity_at: string|undefined = undefined;



    constructor(init?: Partial<JobRun>) {
        Object.assign(this, init);
    }
}
