export class Job{
    id: number = 0;
    name: string = '';
    enabled: boolean = false;
    job_type: string = '';
    hour: number = 0;
    minute: number = 0;
    created_at: string|undefined = undefined;
    updated_at: string|undefined = undefined;
    trigger: string = '';
    param: string =  '';
    weekday: string = '';
    description: string = '';
    grouping_value: string = '';
    ran_last: string|undefined = undefined;

    constructor(init?: Partial<Job>) {
        Object.assign(this, init);
    }
}
