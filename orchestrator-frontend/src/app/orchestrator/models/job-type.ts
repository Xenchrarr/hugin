import {JsonSchema} from './workflow';

export class JobType {

    job_type: string = '';
    function_name: string = '';
    description: string = '';
    input_schema: JsonSchema = {};
    version: number = 1;
    revision_id: string = '';
    active: boolean = false;

    constructor(init?: Partial<JobType>) {
        Object.assign(this, init);
    }
}
