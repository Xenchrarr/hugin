export interface TelegramRelayDestination {
  id: number;
  name: string;
  type: 'webhook' | 'sms' | string;
  config: Record<string, any>;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TelegramRelayRule {
  id: number;
  name: string;
  priority: number;
  enabled: boolean;
  continue_on_match: boolean;
  is_preset: boolean;
  conditions: Record<string, any> | null;
  actions: Record<string, any>[];
  created_at?: string;
  updated_at?: string;
}
