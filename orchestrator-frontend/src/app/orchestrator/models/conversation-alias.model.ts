export interface ConversationAlias {
    id: number;
    owner_user_id: number;
    service: string;
    integration_account: string;
    external_chat_id: string;
    alias: string;
    display_name: string;
    available: boolean;
    created_at: string | null;
    updated_at: string | null;
}

export interface ConversationAliasList {
    conversations: ConversationAlias[];
    more: boolean;
    next_offset: number | null;
}

export interface CreateConversationAlias {
    owner_user_id: number;
    service: string;
    integration_account: string;
    external_chat_id: string;
    alias: string;
    display_name: string;
    available: boolean;
}

export interface UpdateConversationAlias {
    alias: string;
    display_name: string;
    available: boolean;
}
