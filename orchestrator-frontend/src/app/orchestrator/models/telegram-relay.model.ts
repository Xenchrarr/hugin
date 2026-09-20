export interface MessageRelayEndpoint {
  id: number;
  key: string;
  name: string;
  type: 'telegram' | 'sms' | 'webhook' | string;
  enabled: boolean;
  capabilities: string[];
  config: Record<string, any>;
  created_at?: string;
  updated_at?: string;
  runtime_applied?: boolean;
}

export interface MessageRelayTarget {
  endpoint: MessageRelayEndpoint;
  enabled: boolean;
  transform: Record<string, any>;
}

export interface MessageRelayRoute {
  id: number;
  key: string;
  name: string;
  enabled: boolean;
  match_all_sources: boolean;
  filter: Record<string, any> | null;
  is_preset?: boolean;
  sources: MessageRelayEndpoint[];
  targets: MessageRelayTarget[];
  created_at?: string;
  updated_at?: string;
  runtime_applied?: boolean;
}

export interface MessageRelayRouteWrite {
  id: number;
  key: string;
  name: string;
  enabled: boolean;
  match_all_sources: boolean;
  filter: Record<string, any> | null;
  source_endpoint_ids: number[];
  targets: Array<{
    endpoint_id: number;
    enabled: boolean;
    transform: Record<string, any>;
  }>;
}
