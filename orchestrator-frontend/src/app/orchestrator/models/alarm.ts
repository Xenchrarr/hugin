export interface Alarm {
  id: number;
  user_id: number;
  label: string;
  enabled: boolean;
  schedule_type: 'once' | 'daily' | 'weekdays';
  scheduled_at: string | null;
  local_time: string | null;
  weekdays: number[] | null;
  timezone: string;
  ring_seconds: number;
  max_attempts: number;
  retry_interval_seconds: number;
  sms_fallback: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AlarmOccurrence {
  id: number;
  alarm_id: number;
  scheduled_for: string;
  source: string;
  status: string;
  attempt_count: number;
  acknowledged_at?: string;
  completed_at?: string;
  attempts?: {attempt_number: number; status: string; uncertain: boolean; started_at: string}[];
}
