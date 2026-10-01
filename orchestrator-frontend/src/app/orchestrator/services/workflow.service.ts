import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {WorkflowDefinition, WorkflowRunDetail, WorkflowStepType} from '../models/workflow';

@Injectable({providedIn: 'root'})
export class WorkflowService {
    private readonly baseUrl = environment.apiOrchestratorUri + '/workflows';
    constructor(private readonly http: HttpClient) {}

    list(): Observable<WorkflowDefinition[]> {
        return this.http.get<WorkflowDefinition[]>(this.baseUrl + '/list');
    }
    listStepTypes(): Observable<WorkflowStepType[]> {
        return this.http.get<WorkflowStepType[]>(this.baseUrl + '/steps');
    }
    get(key: string): Observable<WorkflowDefinition> {
        return this.http.get<WorkflowDefinition>(`${this.baseUrl}/${encodeURIComponent(key)}`);
    }
    execute(key: string, input: Record<string, unknown>): Observable<{job_run_id: string}> {
        return this.http.post<{job_run_id: string}>(
            `${this.baseUrl}/${encodeURIComponent(key)}/execute`, {input});
    }
    run(id: string): Observable<WorkflowRunDetail> {
        return this.http.get<WorkflowRunDetail>(`${this.baseUrl}/runs/${encodeURIComponent(id)}`);
    }
}
