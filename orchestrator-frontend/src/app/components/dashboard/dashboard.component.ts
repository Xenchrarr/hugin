import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCard, MatCardTitle, MatCardContent } from '@angular/material/card';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { FormsModule } from '@angular/forms';
import { BaseChartDirective } from 'ng2-charts';
import { Chart, ChartData, ChartOptions, ArcElement, BarElement, BarController, DoughnutController, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js';
import { Subject, Subscription, interval, switchMap } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { DashboardService } from '../../services/dashboard.service';
import { DashboardStats } from '../../models/dashboard-stats';
import {TimeService} from '../../services/time.service';


Chart.register(ArcElement, BarElement, BarController, DoughnutController, CategoryScale, LinearScale, Tooltip, Legend);

@Component({
    selector: 'app-dashboard',
    imports: [
        CommonModule,
        MatCard,
        MatCardTitle,
        MatCardContent,
        MatButtonToggleModule,
        MatSlideToggleModule,
        MatIconModule,
        MatButtonModule,
        MatChipsModule,
        FormsModule,
        BaseChartDirective,
    ],
    templateUrl: './dashboard.html',
    styleUrl: './dashboard.scss',
})
export class DashboardComponent implements OnInit, OnDestroy {
    stats: DashboardStats | null = null;
    selectedRange = '30d';
    autoRefresh = true;
    loading = false;

    // Charts
    statusChartData: {
        labels: string[];
        datasets: {
            data: number[];
            backgroundColor: string[];
            borderColor: string[];
            borderWidth: number;
            hoverOffset: number
        }[]
    } = { labels: [], datasets: [] };
    statusChartOptions: ChartOptions<'doughnut'> = {
        responsive: true,
        plugins: { legend: { position: 'bottom' } },
    };

    controlRoomChartData: ChartData<'bar'> = { labels: [], datasets: [] };
    controlRoomChartOptions: ChartOptions<'bar'> = {
        responsive: true,
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
    };

    jobTypeChartData: ChartData<'bar'> = { labels: [], datasets: [] };
    jobTypeChartOptions: ChartOptions<'bar'> = {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    };

    reasonChartData: ChartData<'bar'> = { labels: [], datasets: [] };
    reasonChartOptions: ChartOptions<'bar'> = {
        responsive: true,
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
    };

    private destroy$ = new Subject<void>();
    private refreshSub: Subscription | null = null;

    constructor(private dashboardService: DashboardService,
                private timeService: TimeService) {}

    ngOnInit(): void {
        this.fetchStats();
        this.startAutoRefresh();
    }

    ngOnDestroy(): void {
        this.destroy$.next();
        this.destroy$.complete();
        this.stopAutoRefresh();
    }

    onRangeChange(): void {
        this.fetchStats();
    }

    onAutoRefreshChange(): void {
        if (this.autoRefresh) {
            this.startAutoRefresh();
        } else {
            this.stopAutoRefresh();
        }
    }

    refresh(): void {
        this.fetchStats();
    }

    get successRate(): number {
        if (!this.stats || this.stats.total_runs === 0) return 0;
        const completed = this.stats.runs_by_status.find((s) => s.status === 'Finished');
        return Math.round(((completed?.count ?? 0) / this.stats.total_runs) * 100);
    }

    get topControlRoom(): { name: string; count: number } | null {
        if (!this.stats || this.stats.top_control_rooms.length === 0) return null;
        const top = this.stats.top_control_rooms[0];
        return { name: top.control_room, count: top.count };
    }

    statusColor(status: string): string {
        switch (status) {
            case 'Finished':
                return 'primary';
            case 'Error':
                return 'warn';
            case 'Cancelled':
                return 'accent';
            default:
                return '';
        }
    }

    private fetchStats(): void {
        this.loading = true;
        this.dashboardService
            .getStats(this.selectedRange)
            .pipe(takeUntil(this.destroy$))
            .subscribe({
                next: (data) => {
                    this.stats = data;
                    this.buildCharts(data);
                    this.loading = false;
                },
                error: () => {
                    this.loading = false;
                },
            });
    }

    private startAutoRefresh(): void {
        this.stopAutoRefresh();
        this.refreshSub = interval(60_000)
            .pipe(
                switchMap(() => this.dashboardService.getStats(this.selectedRange)),
                takeUntil(this.destroy$),
            )
            .subscribe((data) => {
                this.stats = data;
                this.buildCharts(data);
            });
    }

    private stopAutoRefresh(): void {
        this.refreshSub?.unsubscribe();
        this.refreshSub = null;
    }

    private readonly STATUS_COLORS: Record<string, string> = {
        Finished: '#4caf50',
        Error: '#f44336',
        Cancelled: '#ff9800',
        Started: '#2196f3',
    };

    private readonly STATUS_BORDER_COLORS: Record<string, string> = {
        Finished: '#388e3c',
        Error: '#c62828',
        Cancelled: '#e65100',
        Started: '#1565c0',
    };

    private statusChartColor(status: string): string {
        return this.STATUS_COLORS[status] ?? '#9e9e9e';
    }

    private statusBorderColor(status: string): string {
        return this.STATUS_BORDER_COLORS[status] ?? '#757575';
    }

    private buildCharts(data: DashboardStats): void {
        // Status doughnut
        this.statusChartData = {
            labels: data.runs_by_status.map((s) => s.status),
            datasets: [
                {
                    data: data.runs_by_status.map((s) => s.count),
                    backgroundColor: data.runs_by_status.map((s) => this.statusChartColor(s.status)),
                    borderColor: data.runs_by_status.map((s) => this.statusBorderColor(s.status)),
                    borderWidth: 2,
                    hoverOffset: 8,
                },
            ],
        };

        // Control room horizontal bar
        this.controlRoomChartData = {
            labels: data.top_control_rooms.map((c) => c.control_room),
            datasets: [
                {
                    data: data.top_control_rooms.map((c) => c.count),
                    backgroundColor: '#7b1fa2',
                },
            ],
        };

        // Job type vertical bar
        this.jobTypeChartData = {
            labels: data.runs_by_job_type.map((j) => j.job_type),
            datasets: [
                {
                    data: data.runs_by_job_type.map((j) => j.count),
                    backgroundColor: '#1976d2',
                },
            ],
        };

        // Reason horizontal bar
        this.reasonChartData = {
            labels: data.reason_counts.map((r) => r.reason),
            datasets: [
                {
                    data: data.reason_counts.map((r) => r.count),
                    backgroundColor: '#00897b',
                },
            ],
        };
    }

    getFormattedDate(date: string): string {
        return this.timeService.formatDate(date);
    }

}
