import {Component, OnInit} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {RouterLink} from '@angular/router';
import {finalize, Observable} from 'rxjs';
import {MonitorService} from '../../services/monitor.service';

@Component({selector: 'app-monitors', standalone: true, imports: [MatButtonModule, MatIconModule, RouterLink], templateUrl: './monitors.component.html', styleUrl: './monitors.component.scss'})
export class MonitorsComponent implements OnInit {
    items: any[] = [];
    loading = true;
    errorMessage = '';
    busyKeys = new Set<string>();
    constructor(private readonly api: MonitorService) {}
    ngOnInit(): void { this.load(); }
    load(): void { this.loading = true; this.errorMessage = ''; this.api.list().pipe(finalize(() => this.loading = false)).subscribe({next: value => this.items = value, error: () => this.errorMessage = 'Monitor health could not be loaded.'}); }
    run(item: any): void { this.withBusy(item.key, this.api.run(item.key)); }
    toggle(item: any): void { this.withBusy(item.key, this.api.enabled(item.key, !item.runtime?.enabled)); }
    status(item: any): string { if (!item.runtime?.enabled) return 'Paused'; if (item.runtime?.last_error) return 'Error'; if (!item.runtime?.last_success_at) return 'Waiting'; return 'Healthy'; }
    private withBusy(key: string, operation: Observable<unknown>): void { this.busyKeys.add(key); operation.pipe(finalize(() => this.busyKeys.delete(key))).subscribe({next: () => this.load(), error: () => this.errorMessage = `Monitor ${key} could not be updated.`}); }
}
