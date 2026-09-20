import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {
    MessageRelayEndpoint,
    MessageRelayRoute,
    MessageRelayRouteWrite
} from '../models/telegram-relay.model';

@Injectable({
    providedIn: 'root'
})
export class TelegramRelayService {
    private baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/telegram_relay';
    }

    // ── Transport-independent endpoints and routes ─────────

    getEndpoints(): Observable<MessageRelayEndpoint[]> {
        return this.http.get<MessageRelayEndpoint[]>(this.baseUrl + '/endpoints');
    }

    saveEndpoint(endpoint: MessageRelayEndpoint): Observable<MessageRelayEndpoint> {
        return this.http.post<MessageRelayEndpoint>(this.baseUrl + '/endpoints', endpoint);
    }

    deleteEndpoint(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/endpoints/' + id);
    }

    getMessageRoutes(): Observable<MessageRelayRoute[]> {
        return this.http.get<MessageRelayRoute[]>(this.baseUrl + '/routes');
    }

    saveMessageRoute(route: MessageRelayRouteWrite): Observable<MessageRelayRoute> {
        return this.http.post<MessageRelayRoute>(this.baseUrl + '/routes', route);
    }

    deleteMessageRoute(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/routes/' + id);
    }

    setMessageRouteEnabled(key: string, enabled: boolean): Observable<MessageRelayRoute> {
        return this.http.patch<MessageRelayRoute>(
            this.baseUrl + '/routes/' + encodeURIComponent(key) + '/enabled',
            {enabled}
        );
    }

    setMessageRouteTargetEnabled(
        routeKey: string,
        endpointKey: string,
        enabled: boolean
    ): Observable<MessageRelayRoute> {
        return this.http.patch<MessageRelayRoute>(
            this.baseUrl + '/routes/' + encodeURIComponent(routeKey)
            + '/targets/' + encodeURIComponent(endpointKey) + '/enabled',
            {enabled}
        );
    }

    // ── Destinations ────────────────────────────────────────

    // ── Rules ────────────────────────────────────────────────

    setPresetEnabled(enabled: boolean): Observable<any> {
        return this.http.patch(this.baseUrl + '/routes/preset/enabled', { enabled });
    }
}
