import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {TelegramRelayDestination, TelegramRelayRule} from '../models/telegram-relay.model';

@Injectable({
    providedIn: 'root'
})
export class TelegramRelayService {
    private baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/telegram_relay';
    }

    // ── Destinations ────────────────────────────────────────

    getDestinations(): Observable<TelegramRelayDestination[]> {
        return this.http.get<TelegramRelayDestination[]>(this.baseUrl + '/destinations');
    }

    saveDestination(destination: TelegramRelayDestination): Observable<TelegramRelayDestination> {
        return this.http.post<TelegramRelayDestination>(this.baseUrl + '/destinations', destination);
    }

    deleteDestination(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/destinations/' + id);
    }

    // ── Rules ────────────────────────────────────────────────

    getRules(): Observable<TelegramRelayRule[]> {
        return this.http.get<TelegramRelayRule[]>(this.baseUrl + '/rules');
    }

    saveRule(rule: TelegramRelayRule): Observable<TelegramRelayRule> {
        return this.http.post<TelegramRelayRule>(this.baseUrl + '/rules', rule);
    }

    deleteRule(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/rules/' + id);
    }

    setPresetEnabled(enabled: boolean): Observable<any> {
        return this.http.patch(this.baseUrl + '/rules/preset/enabled', { enabled });
    }
}
