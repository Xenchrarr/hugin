export interface ScriptParam {
    name: string;
    type: 'string' | 'boolean';
    default: any;
}

export interface Script {
    name: string;
    path: string;
    params: ScriptParam[];
    reason_options: string[];
}
