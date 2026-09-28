import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {Alarm, AlarmOccurrence} from '../models/alarm';

@Injectable({providedIn: 'root'})
export class AlarmService {
  private readonly base = '/api/alarms';
  constructor(private http: HttpClient) {}

  list(): Observable<Alarm[]> { return this.http.get<Alarm[]>(this.base); }
  create(alarm: Partial<Alarm>): Observable<Alarm> { return this.http.post<Alarm>(this.base, alarm); }
  update(id: number, alarm: Partial<Alarm>): Observable<Alarm> { return this.http.put<Alarm>(`${this.base}/${id}`, alarm); }
  delete(id: number): Observable<unknown> { return this.http.delete(`${this.base}/${id}`); }
  action(id: number, action: string, body: object = {}): Observable<any> {
    return this.http.post(`${this.base}/${id}/${action}`, body);
  }
  occurrences(id: number): Observable<AlarmOccurrence[]> {
    return this.http.get<AlarmOccurrence[]>(`${this.base}/${id}/occurrences`);
  }
  cancelOccurrence(_alarmId: number, occurrenceId: number): Observable<unknown> {
    return this.http.post(`${this.base}/occurrences/${occurrenceId}/cancel`, {});
  }
  voiceHealth(): Observable<any> { return this.http.get(`${this.base}/voice-health`); }
}
