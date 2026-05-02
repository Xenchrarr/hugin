export interface LoginResponse {
  token: string;
  user: AuthUser;
}

export interface AuthUser {
  id: number;
  username: string;
  display_name: string | null;
  is_admin: boolean;
}
