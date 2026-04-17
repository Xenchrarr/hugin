import {Injectable} from '@angular/core';
import {HttpClient, HttpContext} from '@angular/common/http';
import {Observable} from 'rxjs';
import {map} from 'rxjs/operators';
import {environment} from '../../../environments/environment';
import {NotificationSetting, Reminder, ReminderHistory} from '../models/reminder';
import {successContext} from '../../core/api-helpers';

@Injectable({
    providedIn: 'root'
})
export class ReminderService {
    private baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/reminders';
    }

    getReminders(status?: string): Observable<Reminder[]> {
        let url = this.baseUrl + '/list';
        if (status) {
            url += '?status=' + status;
        }
        return this.http.get<any[]>(url).pipe(
            map(data => data.map(item => new Reminder(item)))
        );
    }

    getReminder(id: number): Observable<Reminder> {
        return this.http.get<any>(this.baseUrl + '/' + id).pipe(
            map(data => new Reminder(data))
        );
    }

    createReminder(reminder: Partial<Reminder>): Observable<Reminder> {
        return this.http.post<any>(this.baseUrl + '/', reminder,
            successContext('Reminder created')
        ).pipe(
            map(data => new Reminder(data))
        );
    }

    updateReminder(id: number, reminder: Partial<Reminder>): Observable<Reminder> {
        return this.http.put<any>(this.baseUrl + '/' + id, reminder,
            successContext('Reminder updated')
        ).pipe(
            map(data => new Reminder(data))
        );
    }

    deleteReminder(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/' + id,
            successContext('Reminder deleted')
        );
    }

    snoozeReminder(id: number, duration: string = '10m'): Observable<Reminder> {
        return this.http.post<any>(this.baseUrl + '/' + id + '/snooze', {duration},
            successContext('Reminder snoozed')
        ).pipe(
            map(data => new Reminder(data))
        );
    }

    dismissReminder(id: number): Observable<Reminder> {
        return this.http.post<any>(this.baseUrl + '/' + id + '/dismiss', {},
            successContext('Reminder dismissed')
        ).pipe(
            map(data => new Reminder(data))
        );
    }

    getReminderHistory(id: number): Observable<ReminderHistory[]> {
        return this.http.get<any[]>(this.baseUrl + '/' + id + '/history').pipe(
            map(data => data.map(item => new ReminderHistory(item)))
        );
    }

    getNotificationSettings(): Observable<NotificationSetting[]> {
        return this.http.get<any[]>(this.baseUrl + '/notification-settings').pipe(
            map(data => data.map(item => new NotificationSetting(item)))
        );
    }

    updateNotificationSettings(settings: Partial<NotificationSetting>[]): Observable<NotificationSetting[]> {
        return this.http.put<any[]>(this.baseUrl + '/notification-settings', settings,
            successContext('Settings saved')
        ).pipe(
            map(data => data.map(item => new NotificationSetting(item)))
        );
    }

    deleteNotificationSetting(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/notification-settings/' + id,
            successContext('Channel removed')
        );
    }
}
