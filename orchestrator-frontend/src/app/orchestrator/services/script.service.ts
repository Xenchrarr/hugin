import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {catchError, Observable, of} from 'rxjs';
import {map} from 'rxjs/operators';
import {environment} from '../../../environments/environment';
import {Script} from '../models/script';
import {StartJobResponse} from './job.service';

@Injectable({
    providedIn: 'root'
})
export class ScriptService {
    private baseUrl: string;

    constructor(
        private http: HttpClient,
    ) {
        this.baseUrl = environment.apiOrchestratorUri + '/scripts';
    }

    listScripts(): Observable<Script[]> {
        return this.http.get<{ scripts: Script[]; status: number }>(
            `${this.baseUrl}/list`
        ).pipe(
            map(response => response.scripts)
        );
    }

    runScript(scriptName: string, params: Record<string, any>, reason: { selected: string | null; freeText: string | null }): Observable<StartJobResponse | null> {
        const body = {
            script_name: scriptName,
            params: params,
            run_by: 'user',
            reason: reason,
        };
        return this.http.post<StartJobResponse>(`${this.baseUrl}/run`, body).pipe(
            catchError(() => of(null))
        );
    }
}
