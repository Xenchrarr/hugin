import {DatePipe, NgFor, NgIf} from '@angular/common';
import {Component, inject, OnInit} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {MatCard, MatCardContent, MatCardHeader, MatCardTitle} from '@angular/material/card';
import {MatDialog} from '@angular/material/dialog';
import {
    MatCell, MatCellDef, MatColumnDef, MatHeaderCell, MatHeaderCellDef,
    MatHeaderRow, MatHeaderRowDef, MatRow, MatRowDef, MatTable,
} from '@angular/material/table';
import {forkJoin} from 'rxjs';
import {
    MessageHubDelivery,
    MessageHubGatewayStats,
    MessageHubQueueBucket,
    MessageHubStats,
} from '../../models/message-hub.model';
import {MessageHubService} from '../../services/message-hub.service';
import {ConfirmDialogComponent} from '../confirm-dialog/confirm-dialog.component';

@Component({
    selector: 'app-message-hub',
    standalone: true,
    imports: [
        DatePipe, NgFor, NgIf, MatButton, MatCard, MatCardContent, MatCardHeader,
        MatCardTitle, MatCell, MatCellDef, MatColumnDef, MatHeaderCell,
        MatHeaderCellDef, MatHeaderRow, MatHeaderRowDef, MatRow, MatRowDef, MatTable,
    ],
    templateUrl: './message-hub.component.html',
    styleUrl: './message-hub.component.scss',
})
export class MessageHubComponent implements OnInit {
    stats: MessageHubStats = {
        gateways: [],
        open_incidents: [],
        attachments: {count: 0, size_bytes: 0},
    };
    deliveries: MessageHubDelivery[] = [];
    loading = false;
    error = '';
    busy = new Set<number>();
    readonly dialog = inject(MatDialog);
    readonly columns = ['created', 'gateway', 'recipient', 'status', 'message', 'attempts', 'actions'];

    constructor(private hub: MessageHubService) {}

    ngOnInit(): void {
        this.load();
    }

    load(): void {
        this.loading = true;
        this.error = '';
        forkJoin({
            stats: this.hub.getStats(),
            pending: this.hub.getDeliveries('pending'),
            retrying: this.hub.getDeliveries('retry_wait'),
            held: this.hub.getDeliveries('held'),
            dead: this.hub.getDeliveries('dead'),
            uncertain: this.hub.getDeliveries('uncertain'),
        }).subscribe({
            next: result => {
                this.stats = result.stats;
                this.deliveries = [
                    ...result.uncertain, ...result.dead, ...result.held,
                    ...result.retrying, ...result.pending,
                ].sort((a, b) => b.created_at.localeCompare(a.created_at));
                this.loading = false;
            },
            error: error => {
                this.error = error?.error?.message ?? 'Could not load Message Hub status.';
                this.loading = false;
            },
        });
    }

    queueBuckets(gateway: MessageHubGatewayStats): Array<{status: string} & MessageHubQueueBucket> {
        return Object.entries(gateway.deliveries)
            .filter(([, value]) => value.count > 0)
            .map(([status, value]) => ({status, ...value}));
    }

    messageText(delivery: MessageHubDelivery): string {
        return String(delivery.payload['text'] ?? delivery.payload['message'] ?? '<message>');
    }

    attachmentSize(): string {
        const bytes = this.stats.attachments.size_bytes;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    retry(delivery: MessageHubDelivery): void {
        this.run(delivery, () => this.hub.retry(delivery.id));
    }

    confirmRetryAnyway(delivery: MessageHubDelivery): void {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {
                title: 'Retry uncertain delivery',
                message: `Delivery ${delivery.id} may already have been sent. Sending it again can create a duplicate. Continue?`,
                confirmLabel: 'Retry anyway',
            },
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) this.run(delivery, () => this.hub.retryAnyway(delivery.id));
        });
    }

    release(delivery: MessageHubDelivery): void {
        this.run(delivery, () => this.hub.release(delivery.id));
    }

    confirmCancel(delivery: MessageHubDelivery): void {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {
                title: 'Cancel delivery',
                message: `Cancel delivery ${delivery.id} to ${delivery.recipient_key}?`,
                confirmLabel: 'Cancel delivery',
            },
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) this.run(delivery, () => this.hub.cancel(delivery.id));
        });
    }

    private run(delivery: MessageHubDelivery, action: () => ReturnType<MessageHubService['retry']>): void {
        this.busy.add(delivery.id);
        this.error = '';
        action().subscribe({
            next: () => {
                this.busy.delete(delivery.id);
                this.load();
            },
            error: error => {
                this.busy.delete(delivery.id);
                this.error = error?.error?.message ?? `Could not update delivery ${delivery.id}.`;
            },
        });
    }
}
