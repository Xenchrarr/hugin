export class JobApi {
    id: number = 0;
    name: string = '';
    next_run_time: string = '';
    status: string = "";
    trigger: string = "";
    hour: string = "";
    minute: string = "";
    job_id: string = "";

    constructor(init?: Partial<JobApi>) {
        Object.assign(this, init);
    }

}