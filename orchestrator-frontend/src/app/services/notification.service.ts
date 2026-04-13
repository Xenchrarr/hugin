// src/app/core/notification.service.ts
import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable({ providedIn: 'root' })
export class NotificationService {
    constructor(private snack: MatSnackBar) {}

    success(message: string, durationMs = 2500) {
        this.snack.open(message, 'OK', {
            duration: durationMs,
            panelClass: ['snack-success'],
            horizontalPosition: 'right',
            verticalPosition: 'top',
        });
    }

    error(message: string, durationMs = 5000) {
        this.snack.open(message, 'Lukk', {
            duration: durationMs,
            panelClass: ['snack-error'],
            horizontalPosition: 'right',
            verticalPosition: 'top',
        });
    }
}
