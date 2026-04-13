import {Injectable} from '@angular/core';
import {HttpClient, HttpResponse} from '@angular/common/http';
import {catchError, Observable, of, switchMap} from 'rxjs';
import {environment} from "../../../environments/environment";
import {map} from 'rxjs/operators';
import {Job} from "../models/job";
import {MatSnackBar} from "@angular/material/snack-bar";
import {NotificationComponent} from "../components/notification/notification.component";
import {JobApi} from "../models/job-api";
import {JobType} from "../models/job-type";


export interface StartJobResponse {
    message: string;
    status: number;
    job_run_id: string;
}


@Injectable({
    providedIn: 'root'
})
export class JobService {
    baseUrl: string;

    constructor(private http: HttpClient,
                private _snackBar: MatSnackBar) {
        this.baseUrl = environment.apiOrchestratorUri + '/jobs';
        console.log(this.baseUrl);
    }

    getJobs(): Observable<any> {
        console.log(this.baseUrl)
        return this.http.get<any[]>(this.baseUrl + '/list').pipe(
            map(data => data.map(item => new Job(item)))
        );
    }

    // getJobsApi(): Observable<any> {
    //     console.log(this.baseUrl)
    //     return this.http.get<any[]>(this.baseUrl + '/running').pipe(
    //         map(data => data.map(item => new JobApi(item)))
    //     );
    // }

    getJobsApi(): Observable<any> {
        console.log(this.baseUrl);
        return this.http.get<any[]>(this.baseUrl + '/running').pipe(
            map(data =>
                data
                    .map(item => ({
                        ...item,
                        next_run_time: item.next_run_time ? new Date(item.next_run_time) : null
                    })) // Parse next_run_time as Date
                    .sort((a, b) => {
                        if (!a.next_run_time || !b.next_run_time) return 0; // Handle missing dates
                        return a.next_run_time.getTime() - b.next_run_time.getTime(); // Sort by date
                    })
                    .map(item => new JobApi(item)) // Map to JobApi
            )
        );
    }

    getJobTypes(): Observable<any> {
        return this.http.get<any[]>(this.baseUrl + '/types').pipe(
            map(data => data.map(item => new JobType(item)))
        );
    }

    getGroupingValues(): Observable<string[]> {
        return this.http.get<any[]>(this.baseUrl + '/grouping').pipe(
            map(data => data.map(item => String(item))) // Convert each item to a string
        );
    }

    getStatusValues(): Observable<string[]> {
        return this.http.get<any[]>(this.baseUrl + '/status').pipe(
            map(data => data.map(item => String(item))) // Convert each item to a string
        );
    }

    saveJob(job: Job): Observable<any> {
        console.log(job);
        return this.http.post(this.baseUrl + '/', job);
    }

    deleteJob(job: Job): Observable<any> {
        return this.http.delete(this.baseUrl + '/' + job.id);
    }

    getOneJob(jobId: number): Observable<any> {
        return this.http.get<any>(this.baseUrl + '/get_one?job_id=' + jobId).pipe(
            map(data => new Job(data)) // Parse the data into a Job object
        );
    }

    startJob(job: Job): Observable<StartJobResponse | null> {
        const body = { ...job, run_by: 'user' };
        return this.http.post<StartJobResponse>(`${this.baseUrl}/start`, body, { observe: 'response' })
            .pipe(
                switchMap((response: HttpResponse<StartJobResponse>) => {
                    let message = '';
                    switch (response.status) {
                        case 200:
                            message = 'Job started successfully';
                            break;
                        case 400:
                            message = 'Bad Request - Invalid Job Data';
                            break;
                        case 404:
                            message = 'Not Found - Endpoint Does Not Exist';
                            break;
                        case 500:
                            message = 'Internal Server Error - Please Try Again Later';
                            break;
                        default:
                            message = `Unexpected Error - Status Code: ${response.status}`;
                            break;
                    }
                    let data = {
                        message: message,
                        type: 'default'
                    }
                    this._snackBar.openFromComponent(NotificationComponent, {
                        duration: 5000,
                        horizontalPosition: 'center',
                        verticalPosition: 'top',
                        data: data,
                    });
                    return of(response.body);
                }),
                catchError((error) => {
                    const errorMessage = error.error?.message || `Request failed with error: ${error.message}`;
                    let data = {
                        message: errorMessage,
                        type: 'error'
                    }

                    this._snackBar.openFromComponent(NotificationComponent, {
                        duration: 5000,
                        horizontalPosition: 'center',
                        verticalPosition: 'top',
                        data: data,
                    });
                    return of(null);
                })
            );
    }
}
