import {DatePipe, JsonPipe} from '@angular/common';
import {Component, OnInit} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {ActivatedRoute, Router, RouterLink} from '@angular/router';
import {finalize} from 'rxjs';
import {MonitorService} from '../../services/monitor.service';

@Component({selector: 'app-monitor-detail', standalone: true, imports: [DatePipe, JsonPipe, RouterLink, MatButtonModule, MatIconModule], templateUrl: './monitor-detail.component.html', styleUrl: './monitor-detail.component.scss'})
export class MonitorDetailComponent implements OnInit {
    monitor: any = null; errorMessage = ''; loading = true; private readonly key: string;
    constructor(route: ActivatedRoute, private readonly api: MonitorService, private readonly router: Router) { this.key = route.snapshot.paramMap.get('monitorKey') ?? ''; }
    ngOnInit(): void { this.load(); }
    load(): void { this.loading = true; this.api.get(this.key).pipe(finalize(() => this.loading = false)).subscribe({next: value => { this.monitor = value; this.errorMessage = ''; }, error: () => this.errorMessage = 'Monitor could not be loaded.'}); }
    retryable(status: string): boolean { return ['Error','Partial','Cancelled'].includes(status); }
    toggle(): void { if (this.monitor) this.api.enabled(this.key, !this.monitor.runtime?.enabled).subscribe(() => this.load()); }
    retry(id: string): void { this.api.retryIncident(id).subscribe({next: value => void this.router.navigate(['/executions', value.job_run_id]), error: () => this.errorMessage = 'Incident could not be retried.'}); }
}
