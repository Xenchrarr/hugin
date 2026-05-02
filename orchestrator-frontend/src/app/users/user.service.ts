import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { CreateUserPayload, UpdateMePayload, UpdateUserPayload, User } from './user.model';

@Injectable({ providedIn: 'root' })
export class UserService {
  private readonly _base = '/api/users';

  constructor(private http: HttpClient) {}

  list(): Observable<User[]> {
    return this.http.get<User[]>(`${this._base}/list`);
  }

  get(id: number): Observable<User> {
    return this.http.get<User>(`${this._base}/${id}`);
  }

  getMe(): Observable<User> {
    return this.http.get<User>(`${this._base}/me`);
  }

  create(payload: CreateUserPayload): Observable<User> {
    return this.http.post<User>(`${this._base}/`, payload);
  }

  update(id: number, payload: UpdateUserPayload): Observable<User> {
    return this.http.put<User>(`${this._base}/${id}`, payload);
  }

  updateMe(payload: UpdateMePayload): Observable<User> {
    return this.http.put<User>(`${this._base}/me`, payload);
  }

  delete(id: number): Observable<unknown> {
    return this.http.delete(`${this._base}/${id}`);
  }

  getCommandPermissions(id: number): Observable<{ user_id: number; allowed_commands: string[] }> {
    return this.http.get<{ user_id: number; allowed_commands: string[] }>(`${this._base}/${id}/command_permissions`);
  }

  addCommandPermission(id: number, commandPath: string): Observable<unknown> {
    return this.http.post(`${this._base}/${id}/command_permissions`, { command_path: commandPath });
  }

  removeCommandPermission(id: number, commandPath: string): Observable<unknown> {
    return this.http.delete(`${this._base}/${id}/command_permissions/${commandPath}`);
  }
}
