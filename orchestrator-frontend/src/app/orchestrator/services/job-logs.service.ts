import { Injectable } from '@angular/core';
import {HttpClient} from "@angular/common/http";
import {environment} from "../../../environments/environment";
import {Observable} from "rxjs";
import {map} from "rxjs/operators";
import {Job} from "../models/job";
import {JobLog} from "../models/job-log";

@Injectable({
    providedIn: 'root'
})
export class JobLogsService {
    baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/joblog';
    }

    getLogsForJob(jobId: number): Observable<any> {
        return this.http.get<any[]>(this.baseUrl + '/getforjob?job_run_id=' + jobId).pipe(
            map(data => data.map(item => new JobLog(item)))
        );
    }

    getRequestLogsForJob(jobId: number, page: number, pageSize: number): Observable<any> {
        return this.http.get<any[]>(this.baseUrl + '/requests?job_run_id=' + jobId + "&page=" + page + '&page_size=' + pageSize).pipe(
            map(data => data.map(item => new JobLog(item)))
        );
    }

    getTotalNumRequestLogsForJob(jobId: number): Observable<any> {
        return this.http.get<{total:number}>(this.baseUrl + '/requests_total_count?job_run_id=' + jobId).pipe(
            map(response => response.total)
        );
    }
}
