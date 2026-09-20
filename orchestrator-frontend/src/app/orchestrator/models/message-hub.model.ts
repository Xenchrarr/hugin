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
    gateway_key: string;
    recipient_key: string;
    payload: Record<string, unknown>;
    status: string;
    recovery_policy: string;
    attempts: number;
    max_attempts: number;
    created_at: string;
    available_at: string;
    last_error: string | null;
    dispatch_token: string;
}
