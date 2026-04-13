export interface StatusCount {
  status: string;
  count: number;
}

export interface JobTypeCount {
  job_type: string;
  count: number;
}

export interface ControlRoomCount {
  control_room: string;
  count: number;
}

export interface ReasonCount {
  reason: string;
  count: number;
}

export interface RecentRun {
  name: string;
  status: string;
  end_time: string | null;
  parameter: string;
  metadata: Record<string, string>;
}

export interface DashboardStats {
  total_runs: number;
  runs_last_24h: number;
  runs_last_7d: number;
  runs_last_30d: number;
  runs_by_status: StatusCount[];
  runs_by_job_type: JobTypeCount[];
  top_control_rooms: ControlRoomCount[];
  reason_counts: ReasonCount[];
  recent_runs: RecentRun[];
}
