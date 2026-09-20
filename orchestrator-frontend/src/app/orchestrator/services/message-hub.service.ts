import {Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {MessageHubDelivery, MessageHubStats} from '../models/message-hub.model';

@Injectable({providedIn: 'root'})
export class MessageHubService {
    private readonly baseUrl = environment.apiOrchestratorUri + '/message-hub';

    constructor(private http: HttpClient) {}

    getStats(): Observable<MessageHubStats> {
        return this.http.get<MessageHubStats>(this.baseUrl + '/stats');
    }

    getDeliveries(status: string, limit = 200): Observable<MessageHubDelivery[]> {
        const params = new HttpParams().set('status', status).set('limit', limit);
        return this.http.get<MessageHubDelivery[]>(this.baseUrl + '/deliveries', {params});
    }

    retry(id: number): Observable<MessageHubDelivery> {
        return this.http.post<MessageHubDelivery>(`${this.baseUrl}/deliveries/${id}/retry`, {});
    }

    retryAnyway(id: number): Observable<MessageHubDelivery> {
        return this.http.post<MessageHubDelivery>(`${this.baseUrl}/deliveries/${id}/retry-anyway`, {});
    }

    release(id: number): Observable<MessageHubDelivery> {
        return this.http.post<MessageHubDelivery>(`${this.baseUrl}/deliveries/${id}/release`, {});
    }

    cancel(id: number): Observable<MessageHubDelivery> {
        return this.http.post<MessageHubDelivery>(`${this.baseUrl}/deliveries/${id}/cancel`, {});
    }
}
