import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {map} from 'rxjs/operators';
import {environment} from '../../../environments/environment';
import {CalendarEvent, IcalSource} from '../models/ical-source';
import {successContext} from '../../core/api-helpers';

@Injectable({
    providedIn: 'root'
})
export class IcalService {
    private baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/ical_sources';
    }

    getSources(): Observable<IcalSource[]> {
        return this.http.get<any[]>(this.baseUrl + '/list').pipe(
            map(data => data.map(item => new IcalSource(item)))
        );
    }

    createSource(source: Partial<IcalSource>): Observable<IcalSource> {
        return this.http.post<any>(this.baseUrl + '/', source,
            successContext('Calendar source added')
        ).pipe(map(data => new IcalSource(data)));
    }

    updateSource(id: number, source: Partial<IcalSource>): Observable<IcalSource> {
        return this.http.put<any>(this.baseUrl + '/' + id, source,
            successContext('Calendar source updated')
        ).pipe(map(data => new IcalSource(data)));
    }

    deleteSource(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/' + id,
            successContext('Calendar source deleted')
        );
    }

    getAgenda(days: number = 14): Observable<CalendarEvent[]> {
        return this.http.get<any>(this.baseUrl + '/agenda?days=' + days).pipe(
            map(data => data.events as CalendarEvent[])
        );
    }
}
