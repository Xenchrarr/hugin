export interface UserConfig {
  weather_location_id?: string;
  inverter_type?: 'growatt' | 'ecoflow' | 'deye' | null;
  inverter_id?: string;
  growatt_username?: string;
  growatt_password?: string;
  deye_app_id?: string;
  deye_app_secret?: string;
  deye_email?: string;
  deye_password?: string;
  deye_device_sn?: string;
  default_channels?: string[];
  pin?: string;
}

export interface User {
  id: number;
  username: string;
  display_name: string | null;
  phone_number: string | null;
  telegram_user_id: number | null;
  config: UserConfig;
  is_admin: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateUserPayload {
  username: string;
  password: string;
  display_name?: string;
  phone_number?: string;
  telegram_user_id?: number | null;
  config?: UserConfig;
  is_admin?: boolean;
}

export interface UpdateUserPayload {
  display_name?: string;
  phone_number?: string | null;
  telegram_user_id?: number | null;
  config?: UserConfig;
  password?: string;
  is_admin?: boolean;
}

export interface UpdateMePayload {
  display_name?: string;
  phone_number?: string | null;
  telegram_user_id?: number | null;
  config?: UserConfig;
  password?: string;
  current_password?: string;
}
