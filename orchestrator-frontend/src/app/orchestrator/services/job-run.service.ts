
import {Injectable} from '@angular/core';
import {HttpClient} from "@angular/common/http";
import {environment} from "../../../environments/environment";
import {Observable} from "rxjs";
import {map} from "rxjs/operators";
import {Job} from "../models/job";
import {JobRun} from '../models/job-run';

@Injectable({
    providedIn: 'root'
})
export class JobRunService {
    baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/jobrun';
    }

    getJobRuns(page: number, pageSize: number, groupingValues: string[], statusValues:string[]): Observable<any> {
        let grouping = ""
        if (groupingValues.length > 0) {
            grouping = "&grouping=" + groupingValues.join(",");
        }
        if (statusValues.length > 0) {

            grouping += "&status=" + statusValues.join(",");
        }

        return this.http.get<any[]>(this.baseUrl + '/list?page=' + page + '&page_size=' + pageSize + grouping).pipe(
            map(data => data.map(item => new JobRun(item)))
        );
    }

    getTotalJobRuns(groupingValues: string[], statusValues: string[]): Observable<any> {
        let grouping = ""
        if (groupingValues.length > 0) {
            grouping = "?grouping=" + groupingValues.join(",");
        }
        if (statusValues.length > 0) {
            if (grouping.length > 0) {
                grouping += "&";
            } else  {
                grouping += "?";
            }
            grouping += "&status=" + statusValues.join(",");
        }
        return this.http.get<{total:number}>(this.baseUrl + '/total_count' + grouping).pipe(
            map(response => response.total)
        );
    }

    getJobRun(jobRunId: number | string): Observable<JobRun> {
        return this.http.get<any>(this.baseUrl + '/get?job_run_id=' + jobRunId).pipe(
            map(data => new JobRun(data))
        );
    }

    cancelJobRun(jobRunId: string): Observable<any> {
        return this.http.post(this.baseUrl + '/cancel', { job_run_id: jobRunId });
    }

    deleteJobRun(jobRunId: string): Observable<any> {
        return this.http.request('delete', this.baseUrl + '/delete', { body: { job_run_id: jobRunId } });
    }
}
