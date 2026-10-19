import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {
    ConversationAlias,
    ConversationAliasList,
    CreateConversationAlias,
    UpdateConversationAlias,
} from '../models/conversation-alias.model';

@Injectable({providedIn: 'root'})
export class ConversationAliasService {
    private readonly baseUrl = environment.apiOrchestratorUri + '/sms-routing/conversations';

    constructor(private http: HttpClient) {}

    list(): Observable<ConversationAliasList> {
        return this.http.get<ConversationAliasList>(this.baseUrl, {
            params: {limit: 500},
        });
    }

    create(value: CreateConversationAlias): Observable<ConversationAlias> {
        return this.http.post<ConversationAlias>(this.baseUrl, value);
    }

    update(id: number, value: UpdateConversationAlias): Observable<ConversationAlias> {
        return this.http.put<ConversationAlias>(`${this.baseUrl}/${id}`, value);
    }

    delete(id: number): Observable<{message: string}> {
        return this.http.delete<{message: string}>(`${this.baseUrl}/${id}`);
    }
}
