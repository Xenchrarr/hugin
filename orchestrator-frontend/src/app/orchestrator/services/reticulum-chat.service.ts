import {HttpClient, HttpParams} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {
    ReticulumAnnounce,
    ReticulumAnnounceResult,
    ReticulumAnnounceTarget,
    ReticulumConversation,
    ReticulumMessage,
    ReticulumStatus,
    SendReticulumMessage,
} from '../models/reticulum-chat.model';

@Injectable({providedIn: 'root'})
export class ReticulumChatService {
    private readonly baseUrl = environment.apiOrchestratorUri + '/reticulum-chat';

    constructor(private http: HttpClient) {}

    status(): Observable<ReticulumStatus> {
        return this.http.get<ReticulumStatus>(`${this.baseUrl}/status`);
    }

    conversations(limit = 100): Observable<ReticulumConversation[]> {
        return this.http.get<ReticulumConversation[]>(`${this.baseUrl}/conversations`, {
            params: new HttpParams().set('limit', limit),
        });
    }

    messages(destinationHash: string, limit = 100): Observable<ReticulumMessage[]> {
        return this.http.get<ReticulumMessage[]>(
            `${this.baseUrl}/conversations/${destinationHash}/messages`,
            {params: new HttpParams().set('limit', limit)},
        );
    }

    markRead(destinationHash: string): Observable<{status: string}> {
        return this.http.post<{status: string}>(
            `${this.baseUrl}/conversations/${destinationHash}/read`,
            {},
        );
    }

    send(message: SendReticulumMessage): Observable<ReticulumMessage> {
        return this.http.post<ReticulumMessage>(`${this.baseUrl}/messages`, message);
    }

    announces(limit = 100, aspect = ''): Observable<ReticulumAnnounce[]> {
        let params = new HttpParams().set('limit', limit);
        if (aspect) params = params.set('aspect', aspect);
        return this.http.get<ReticulumAnnounce[]>(`${this.baseUrl}/announces`, {params});
    }

    announce(target: ReticulumAnnounceTarget): Observable<ReticulumAnnounceResult> {
        return this.http.post<ReticulumAnnounceResult>(`${this.baseUrl}/announce`, {target});
    }
}
