import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {
    WorkflowCatalogItem, WorkflowDefinition, WorkflowDraft, WorkflowEditorDefinition,
    WorkflowRunDetail, WorkflowStepType,
} from '../models/workflow';

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
    catalog(): Observable<WorkflowCatalogItem[]> {
        return this.http.get<WorkflowCatalogItem[]>(this.baseUrl + '/manage');
    }
    get(key: string): Observable<WorkflowDefinition> {
        return this.http.get<WorkflowDefinition>(`${this.baseUrl}/${encodeURIComponent(key)}`);
    }
    create(key: string, name: string, description: string): Observable<WorkflowDraft> {
        return this.http.post<WorkflowDraft>(this.baseUrl + '/', {key, name, description});
    }
    draft(key: string): Observable<WorkflowDraft> {
        return this.http.get<WorkflowDraft>(`${this.baseUrl}/${encodeURIComponent(key)}/draft`);
    }
    saveDraft(key: string, name: string, description: string,
              editor_definition: WorkflowEditorDefinition, lock_version: number): Observable<WorkflowDraft> {
        return this.http.put<WorkflowDraft>(`${this.baseUrl}/${encodeURIComponent(key)}/draft`,
            {name, description, editor_definition, lock_version});
    }
    validate(key: string, editor_definition: WorkflowEditorDefinition): Observable<{valid: boolean; compiled_definition: WorkflowDefinition}> {
        return this.http.post<{valid: boolean; compiled_definition: WorkflowDefinition}>(
            `${this.baseUrl}/${encodeURIComponent(key)}/validate`, {editor_definition});
    }
    publish(key: string, name: string, description: string, editor_definition: WorkflowEditorDefinition,
            lock_version: number): Observable<WorkflowDraft> {
        return this.http.post<WorkflowDraft>(`${this.baseUrl}/${encodeURIComponent(key)}/publish`,
            {name, description, editor_definition, lock_version});
    }
    revisions(key: string): Observable<WorkflowDraft[]> {
        return this.http.get<WorkflowDraft[]>(`${this.baseUrl}/${encodeURIComponent(key)}/revisions`);
    }
    cloneRevision(key: string, version: number, lock_version: number): Observable<WorkflowDraft> {
        return this.http.post<WorkflowDraft>(
            `${this.baseUrl}/${encodeURIComponent(key)}/revisions/${version}/clone`, {lock_version});
    }
    archive(key: string): Observable<{message: string}> {
        return this.http.post<{message: string}>(`${this.baseUrl}/${encodeURIComponent(key)}/archive`, {});
    }
    execute(key: string, input: Record<string, unknown>): Observable<{job_run_id: string}> {
        return this.http.post<{job_run_id: string}>(
            `${this.baseUrl}/${encodeURIComponent(key)}/execute`, {input});
    }
    run(id: string): Observable<WorkflowRunDetail> {
        return this.http.get<WorkflowRunDetail>(`${this.baseUrl}/runs/${encodeURIComponent(id)}`);
    }
}
