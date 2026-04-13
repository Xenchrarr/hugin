import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { DashboardStats } from '../models/dashboard-stats';

@Injectable({
  providedIn: 'root',
})
export class DashboardService {
  private readonly baseUrl = `${environment.apiOrchestratorUri}/dashboard`;

  constructor(private http: HttpClient) {}

  getStats(range: string = '30d'): Observable<DashboardStats> {
    return this.http
      .get<DashboardStats & { status: number }>(`${this.baseUrl}/stats`, {
        params: { range },
      })
      .pipe(map(({ status, ...stats }) => stats as DashboardStats));
  }
}
