export class JobType {

    job_type: string = '';
    function_name: string = '';
    description: string = '';

    constructor(init?: Partial<JobType>) {
        Object.assign(this, init);
    }
}
