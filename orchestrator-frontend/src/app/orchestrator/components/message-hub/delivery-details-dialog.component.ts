import {DatePipe, JsonPipe, NgFor, NgIf} from '@angular/common';
import {Component, Inject, OnInit} from '@angular/core';
import {MatButton} from '@angular/material/button';
import {
    MAT_DIALOG_DATA,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogRef,
    MatDialogTitle,
} from '@angular/material/dialog';
import {MessageHubDelivery, MessageHubDeliveryDetails} from '../../models/message-hub.model';
import {MessageHubService} from '../../services/message-hub.service';

export type DeliveryDetailsAction =
    'acknowledge' | 'cancel' | 'release' | 'retry' | 'retry-anyway';

export interface DeliveryDetailsDialogResult {
    action: DeliveryDetailsAction;
    delivery: MessageHubDelivery;
}

@Component({
    selector: 'app-delivery-details-dialog',
    standalone: true,
    imports: [
        DatePipe, JsonPipe, NgFor, NgIf, MatButton, MatDialogActions, MatDialogClose,
        MatDialogContent, MatDialogTitle,
    ],
    templateUrl: './delivery-details-dialog.component.html',
    styleUrl: './delivery-details-dialog.component.scss',
})
export class DeliveryDetailsDialogComponent implements OnInit {
    details: MessageHubDeliveryDetails | null = null;
    loading = true;
    error = '';

    constructor(
        @Inject(MAT_DIALOG_DATA) readonly deliveryId: number,
        private readonly hub: MessageHubService,
        private readonly dialogRef: MatDialogRef<DeliveryDetailsDialogComponent>,
    ) {}

    ngOnInit(): void {
        this.hub.getDeliveryDetails(this.deliveryId).subscribe({
            next: details => {
                this.details = details;
                this.loading = false;
            },
            error: error => {
                this.error = error?.error?.message ?? 'Could not load delivery details.';
                this.loading = false;
            },
        });
    }

    choose(action: DeliveryDetailsAction): void {
        if (!this.details) return;
        this.dialogRef.close({action, delivery: this.details.delivery});
    }

    messageText(): string {
        const payload = this.details?.delivery.payload;
        return String(payload?.['text'] ?? payload?.['message'] ?? '<message>');
    }

    formatBytes(bytes: number): string {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}
