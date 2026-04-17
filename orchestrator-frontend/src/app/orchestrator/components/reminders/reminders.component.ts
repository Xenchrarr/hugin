import {Component, inject, OnInit} from '@angular/core';
import {NotificationSetting, Reminder} from '../../models/reminder';
import {ReminderService} from '../../services/reminder.service';
import {MatButton} from '@angular/material/button';
import {
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell,
    MatHeaderCellDef,
    MatHeaderRow,
    MatHeaderRowDef,
    MatRow,
    MatRowDef,
    MatTable
} from '@angular/material/table';
import {MatChip, MatChipSet} from '@angular/material/chips';
import {NgIf, NgFor, DatePipe} from '@angular/common';
import {MatDialog} from '@angular/material/dialog';
import {MatButtonToggle, MatButtonToggleGroup} from '@angular/material/button-toggle';
import {ReminderDialogComponent} from './reminder-dialog/reminder-dialog.component';
import {ConfirmDialogComponent} from '../confirm-dialog/confirm-dialog.component';

@Component({
    selector: 'app-reminders',
    standalone: true,
    imports: [
        MatButton,
        MatCell,
        MatCellDef,
        MatColumnDef,
        MatHeaderCell,
        MatHeaderCellDef,
        MatHeaderRow,
        MatHeaderRowDef,
        MatRow,
        MatRowDef,
        MatTable,
        MatChip,
        MatChipSet,
        MatButtonToggle,
        MatButtonToggleGroup,
        NgIf,
        NgFor,
        DatePipe,
    ],
    templateUrl: './reminders.component.html',
    styleUrl: './reminders.component.scss'
})
export class RemindersComponent implements OnInit {
    reminders: Reminder[] = [];
    notificationSettings: NotificationSetting[] = [];
    statusFilter: string = 'active';
    readonly dialog = inject(MatDialog);

    displayedColumns: string[] = ['title', 'due_at', 'recurrence', 'status', 'recipients', 'created_by', 'actions'];

    constructor(private reminderService: ReminderService) {
    }

    ngOnInit() {
        this.loadReminders();
        this.reminderService.getNotificationSettings().subscribe(settings => {
            this.notificationSettings = settings;
        });
    }

    loadReminders() {
        this.reminderService.getReminders(this.statusFilter).subscribe(reminders => {
            this.reminders = reminders;
        });
    }

    getRecipientLabels(reminder: Reminder): string[] {
        if (!reminder.recipient_ids?.length) return [];
        return reminder.recipient_ids
            .map(id => this.notificationSettings.find(s => s.id === id))
            .filter(s => !!s)
            .map(s => s!.user_label ? `${s!.user_label} (${s!.channel})` : s!.channel);
    }

    onStatusFilterChange(status: string) {
        this.statusFilter = status;
        this.loadReminders();
    }

    addReminder() {
        const dialogRef = this.dialog.open(ReminderDialogComponent, {
            data: undefined,
            width: '600px',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.loadReminders();
            }
        });
    }

    editReminder(reminder: Reminder) {
        const dialogRef = this.dialog.open(ReminderDialogComponent, {
            data: reminder,
            width: '600px',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.loadReminders();
            }
        });
    }

    snoozeReminder(reminder: Reminder) {
        this.reminderService.snoozeReminder(reminder.id).subscribe(() => {
            this.loadReminders();
        });
    }

    dismissReminder(reminder: Reminder) {
        this.reminderService.dismissReminder(reminder.id).subscribe(() => {
            this.loadReminders();
        });
    }

    confirmDeleteReminder(reminder: Reminder): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            data: {title: 'Delete Reminder?', message: `Are you sure you want to delete "${reminder.title}"?`, confirmLabel: 'Delete'},
            width: '400px',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.reminderService.deleteReminder(reminder.id).subscribe({
                    next: () => this.loadReminders(),
                    error: () => this.loadReminders(),
                });
            }
        });
    }
}
