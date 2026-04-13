export class JobLog {
    // JOB_RUN_ID, LOG_LEVEL, TIMESTAMP, MESSAGE
    id: number = 0;
    job_run_id: number = 0;
    log_level: string = '';
    created_at: string = '';
    message: string = '';
    stack_trace: string = '';

    constructor(init?: Partial<JobLog>) {
        Object.assign(this, init);
    }
}
