export interface MessageHubQueueBucket {
    count: number;
    oldest_at: string | null;
}

export interface MessageHubGatewayStats {
    gateway_key: string;
    name: string;
    health: string;
    deliveries: Record<string, MessageHubQueueBucket>;
}

export interface MessageHubIncident {
    id: number;
    gateway_key: string;
    error: string | null;
    opened_at: string;
}

export interface MessageHubStats {
    gateways: MessageHubGatewayStats[];
    open_incidents: MessageHubIncident[];
    attachments: {
        count: number;
        size_bytes: number;
    };
}

export interface MessageHubDelivery {
    id: number;
    message_id: number;
    gateway_id: number;
    gateway_key: string;
    recipient_key: string;
    target_endpoint_id: number | null;
    route_id: number | null;
    address: Record<string, unknown>;
    payload: Record<string, unknown>;
    status: string;
    recovery_policy: string;
    priority: number;
    attempts: number;
    max_attempts: number;
    created_at: string;
    updated_at: string;
    available_at: string;
    leased_until: string | null;
    accepted_at: string | null;
    expired_at: string | null;
    recovery_notified_at: string | null;
    acknowledged_at: string | null;
    last_error: string | null;
    dispatch_token: string;
    source_type: string | null;
    source_label: string | null;
    conversation_key: string | null;
}

export type MessageHubBulkAction = 'acknowledge' | 'cancel' | 'release' | 'retry';

export interface MessageHubBulkResult {
    requested: number;
    updated: number;
    updated_ids: number[];
    skipped: Array<{
        id: number;
        reason: string;
        status: string | null;
    }>;
    operation?: MessageHubBulkOperation | null;
}

export interface MessageHubBulkOperation {
    id: number;
    action: MessageHubBulkAction;
    scope: 'selection' | 'filter' | 'group';
    actor_user_id: number | null;
    actor_username: string | null;
    status: 'in_progress' | 'completed' | 'partially_undone' | 'undone';
    affected_count: number;
    undone_count: number;
    filter_snapshot: Record<string, unknown>;
    created_at: string;
    completed_at: string | null;
    undo_expires_at: string | null;
    undone_at: string | null;
    can_undo: boolean;
    can_resume: boolean;
}

export interface MessageHubBulkUndoResult {
    operation: MessageHubBulkOperation;
    restored: number;
    restored_ids: number[];
    skipped: number;
}

export interface MessageHubFilteredBulkResult extends MessageHubBulkResult {
    matching: number;
    remaining: number;
    truncated: boolean;
}

export interface MessageHubDeliveryPage {
    items: MessageHubDelivery[];
    total: number;
    page: number;
    page_size: number;
}

export interface MessageHubDeliveryFilters {
    statuses: string[];
    page: number;
    pageSize: number;
    gatewayKey?: string;
    recipient?: string;
    query?: string;
    createdAfter?: string;
    createdBefore?: string;
    sort?: 'asc' | 'desc';
    sourceType?: string;
    sourceLabel?: string;
    sourceLabelExact?: string;
    conversationKey?: string;
}

export interface MessageHubDeliveryGroup {
    gateway_key: string;
    recipient_key: string;
    source_type: string;
    source_label: string;
    conversation_key: string | null;
    count: number;
    oldest_at: string;
    newest_at: string;
    preview: string;
}

export interface MessageHubDeliveryGroupPage {
    items: MessageHubDeliveryGroup[];
    total: number;
    page: number;
    page_size: number;
}

export interface MessageHubGroupBulkResult extends MessageHubBulkResult {
    matching: number;
    truncated: boolean;
}

export interface MessageHubMessageDetails {
    id: number;
    direction: string;
    kind: string;
    source_gateway_id: number | null;
    source_endpoint_id: number | null;
    external_id: string | null;
    conversation_key: string | null;
    payload: Record<string, unknown>;
    metadata: Record<string, unknown>;
    priority: number;
    created_at: string;
    expires_at: string;
}

export interface MessageHubAttachmentDetails {
    id: number;
    filename: string | null;
    content_type: string;
    size_bytes: number;
    sha256: string;
    created_at: string;
}

export interface MessageHubAttemptDetails {
    id: number;
    attempt_number: number;
    outcome: string;
    provider_reference: string | null;
    error: string | null;
    started_at: string;
    completed_at: string;
}

export interface MessageHubDeliveryDetails {
    delivery: MessageHubDelivery;
    message: MessageHubMessageDetails;
    attachments: MessageHubAttachmentDetails[];
    attempts: MessageHubAttemptDetails[];
}
