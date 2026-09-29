export interface ReticulumStatus {
    status: string;
    ready: boolean;
    delivery_hash: string | null;
    propagation_hash: string | null;
    site_hash: string | null;
    propagation_enabled: boolean;
    last_manual_announce_at: number | null;
}

export type ReticulumAnnounceTarget = 'delivery' | 'site' | 'propagation' | 'all';

export interface ReticulumAnnounce {
    destination_hash: string;
    identity_hash: string | null;
    aspect: 'lxmf.delivery' | 'lxmf.propagation' | 'nomadnetwork.node' | 'unknown';
    display_name: string | null;
    app_data_text: string | null;
    first_seen: number;
    received_at: number;
    seen_count: number;
    hops: number | null;
    announce_packet_hash: string | null;
    is_path_response: boolean;
}

export interface ReticulumAnnounceResult {
    announced_at: number;
    targets: Array<{target: Exclude<ReticulumAnnounceTarget, 'all'>; destination_hash: string}>;
}

export interface ReticulumConversation {
    index: number;
    destination_hash: string;
    display_name: string;
    last_text: string;
    timestamp: number;
    unread_count: number;
}

export interface ReticulumMessage {
    id: number;
    message_hash: string;
    client_token: string | null;
    conversation_hash: string;
    direction: 'inbound' | 'outbound';
    text: string;
    title: string;
    timestamp: number;
    created_at: number;
    state: 'received' | 'queued' | 'sending' | 'sent' | 'stored' | 'delivered' | 'failed' | 'rejected';
    delivery_method: 'direct' | 'opportunistic' | 'propagated' | 'paper' | null;
    progress: number;
    error: string | null;
    signature_validated: boolean | null;
    transport_encrypted: boolean | null;
    transport_encryption: string | null;
    rssi: number | null;
    snr: number | null;
    quality: number | null;
}

export interface SendReticulumMessage {
    destination_hash: string;
    text: string;
    title?: string;
    delivery_method: 'direct' | 'opportunistic' | 'propagated';
    client_token: string;
}
