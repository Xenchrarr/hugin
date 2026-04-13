import { Injectable } from '@angular/core';
import {HttpClient, HttpResponse} from "@angular/common/http";
import {environment} from "../../../environments/environment";
import {catchError, Observable, of} from "rxjs";
import {map} from "rxjs/operators";

@Injectable({
    providedIn: 'root'
})
export class ConnectionStatusService {
    baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/connection_status';
    }

    getStatus(statusItem: string): Observable<any> {
        return this.http.get<any>(this.baseUrl + '/status?status_item=' + statusItem);

    }

    getStatusItems(): Observable<any> {
        return this.http.get<any[]>(this.baseUrl + '/status_items');
    }

    checkIfBackendIsUp(): Observable<boolean> {
        return this.http.get<any>(this.baseUrl + '/health', { observe: 'response' }).pipe(
            map((response: HttpResponse<any>) => response.status === 200),
            catchError(() => of(false))
        );
    }
}
