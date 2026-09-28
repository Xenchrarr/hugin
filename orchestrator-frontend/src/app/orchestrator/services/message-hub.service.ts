import {Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {environment} from '../../../environments/environment';
import {
    MessageHubBulkAction,
    MessageHubBulkResult,
    MessageHubBulkOperation,
    MessageHubBulkUndoResult,
    MessageHubDelivery,
    MessageHubDeliveryFilters,
    MessageHubDeliveryGroup,
    MessageHubDeliveryGroupPage,
    MessageHubDeliveryDetails,
    MessageHubDeliveryPage,
    MessageHubFilteredBulkResult,
    MessageHubGroupBulkResult,
    MessageHubStats,
} from '../models/message-hub.model';

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

    getDeliveryDetails(id: number): Observable<MessageHubDeliveryDetails> {
        return this.http.get<MessageHubDeliveryDetails>(`${this.baseUrl}/deliveries/${id}`);
    }

    searchDeliveries(filters: MessageHubDeliveryFilters): Observable<MessageHubDeliveryPage> {
        return this.http.get<MessageHubDeliveryPage>(this.baseUrl + '/deliveries/search', {
            params: this.searchParams(filters),
        });
    }

    searchDeliveryGroups(filters: MessageHubDeliveryFilters): Observable<MessageHubDeliveryGroupPage> {
        return this.http.get<MessageHubDeliveryGroupPage>(this.baseUrl + '/delivery-groups/search', {
            params: this.searchParams(filters),
        });
    }

    private searchParams(filters: MessageHubDeliveryFilters): HttpParams {
        let params = new HttpParams()
            .set('statuses', filters.statuses.join(','))
            .set('page', filters.page)
            .set('page_size', filters.pageSize);
        if (filters.gatewayKey) params = params.set('gateway_key', filters.gatewayKey);
        if (filters.recipient) params = params.set('recipient', filters.recipient);
        if (filters.query) params = params.set('query', filters.query);
        if (filters.createdAfter) params = params.set('created_after', filters.createdAfter);
        if (filters.createdBefore) params = params.set('created_before', filters.createdBefore);
        if (filters.sort) params = params.set('sort', filters.sort);
        if (filters.sourceType) params = params.set('source_type', filters.sourceType);
        if (filters.sourceLabel) params = params.set('source_label', filters.sourceLabel);
        if (filters.sourceLabelExact) params = params.set('source_label_exact', filters.sourceLabelExact);
        if (filters.conversationKey !== undefined) {
            params = params.set('conversation_key', filters.conversationKey);
        }
        return params;
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

    bulkAction(deliveryIds: number[], action: MessageHubBulkAction): Observable<MessageHubBulkResult> {
        return this.http.post<MessageHubBulkResult>(`${this.baseUrl}/deliveries/bulk-action`, {
            delivery_ids: deliveryIds,
            action,
        });
    }

    bulkFilteredAction(
        filters: MessageHubDeliveryFilters,
        action: MessageHubBulkAction,
        operationId?: number,
    ): Observable<MessageHubFilteredBulkResult> {
        return this.http.post<MessageHubFilteredBulkResult>(
            `${this.baseUrl}/deliveries/bulk-filter-action`,
            {
                action,
                operation_id: operationId,
                filters: {
                    statuses: filters.statuses,
                    gateway_key: filters.gatewayKey,
                    recipient: filters.recipient,
                    query: filters.query,
                    created_after: filters.createdAfter,
                    created_before: filters.createdBefore,
                    source_type: filters.sourceType,
                    source_label: filters.sourceLabel,
                    source_label_exact: filters.sourceLabelExact,
                    conversation_key: filters.conversationKey,
                },
            },
        );
    }

    getBulkOperations(limit = 20): Observable<MessageHubBulkOperation[]> {
        const params = new HttpParams().set('limit', limit);
        return this.http.get<MessageHubBulkOperation[]>(`${this.baseUrl}/bulk-operations`, {params});
    }

    undoBulkOperation(operationId: number): Observable<MessageHubBulkUndoResult> {
        return this.http.post<MessageHubBulkUndoResult>(
            `${this.baseUrl}/bulk-operations/${operationId}/undo`,
            {},
        );
    }

    resumeBulkOperation(operationId: number): Observable<MessageHubFilteredBulkResult> {
        return this.http.post<MessageHubFilteredBulkResult>(
            `${this.baseUrl}/bulk-operations/${operationId}/resume`,
            {},
        );
    }

    bulkGroupAction(
        group: MessageHubDeliveryGroup,
        action: MessageHubBulkAction,
        filters: MessageHubDeliveryFilters,
    ): Observable<MessageHubGroupBulkResult> {
        return this.http.post<MessageHubGroupBulkResult>(
            `${this.baseUrl}/delivery-groups/bulk-action`,
            {
                action,
                statuses: filters.statuses,
                gateway_key: group.gateway_key,
                recipient_key: group.recipient_key,
                source_type: group.source_type,
                source_label: group.source_label,
                conversation_key: group.conversation_key ?? '',
                query: filters.query,
                created_after: filters.createdAfter,
                created_before: filters.createdBefore,
            },
        );
    }
}
