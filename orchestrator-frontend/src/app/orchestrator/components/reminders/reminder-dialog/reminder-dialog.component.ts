import {Component, Inject, OnInit} from '@angular/core';
import {
    MAT_DIALOG_DATA,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogRef,
    MatDialogTitle
} from '@angular/material/dialog';
import {MatButton} from '@angular/material/button';
import {MatCard, MatCardContent} from '@angular/material/card';
import {MatCheckbox} from '@angular/material/checkbox';
import {MatFormField, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {MatSelect} from '@angular/material/select';
import {MatOption} from '@angular/material/core';
import {FormsModule} from '@angular/forms';
import {NgIf, NgFor} from '@angular/common';
import {NotificationSetting, Reminder} from '../../../models/reminder';
import {ReminderService} from '../../../services/reminder.service';

@Component({
    selector: 'app-reminder-dialog',
    standalone: true,
    imports: [
        MatButton,
        MatDialogActions,
        MatDialogClose,
        MatDialogContent,
        MatDialogTitle,
        MatCard,
        MatCardContent,
        MatCheckbox,
        MatFormField,
        MatInput,
        MatLabel,
        MatSelect,
        MatOption,
        FormsModule,
        NgIf,
        NgFor,
    ],
    templateUrl: './reminder-dialog.component.html',
    styleUrl: './reminder-dialog.component.scss'
})
export class ReminderDialogComponent implements OnInit {
    reminder: Reminder;
    isNew = false;
    dueDate: string = '';
    dueTime: string = '';

    notificationSettings: NotificationSetting[] = [];
    selectedRecipientIds: number[] = [];

    recurrenceOptions = [
        {value: '', label: 'One-time'},
        {value: 'daily', label: 'Daily'},
        {value: 'weekly:mon', label: 'Weekly (Monday)'},
        {value: 'weekly:tue', label: 'Weekly (Tuesday)'},
        {value: 'weekly:wed', label: 'Weekly (Wednesday)'},
        {value: 'weekly:thu', label: 'Weekly (Thursday)'},
        {value: 'weekly:fri', label: 'Weekly (Friday)'},
        {value: 'weekly:sat', label: 'Weekly (Saturday)'},
        {value: 'weekly:sun', label: 'Weekly (Sunday)'},
        {value: 'interval:1h', label: 'Every hour'},
        {value: 'interval:30m', label: 'Every 30 minutes'},
        {value: 'interval:2d', label: 'Every 2 days'},
        {value: 'interval:3d', label: 'Every 3 days'},
        {value: 'interval:7d', label: 'Every 7 days'},
    ];

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: Reminder,
        private reminderService: ReminderService,
        private dialogRef: MatDialogRef<ReminderDialogComponent>
    ) {
        if (!data) {
            this.reminder = new Reminder();
            this.isNew = true;
            const now = new Date();
            now.setMinutes(now.getMinutes() + 30);
            this.dueDate = this.toDateString(now);
            this.dueTime = this.toTimeString(now);
        } else {
            this.reminder = new Reminder(data);
            if (this.reminder.due_at) {
                const d = new Date(this.reminder.due_at);
                this.dueDate = this.toDateString(d);
                this.dueTime = this.toTimeString(d);
            }
            this.selectedRecipientIds = this.reminder.recipient_ids ? [...this.reminder.recipient_ids] : [];
        }
    }

    ngOnInit() {
        this.reminderService.getNotificationSettings().subscribe(settings => {
            this.notificationSettings = settings;
        });
    }

    recipientLabel(setting: NotificationSetting): string {
        return setting.user_label ? `${setting.user_label} (${setting.channel})` : setting.channel;
    }

    save() {
        this.reminder.due_at = new Date(this.dueDate + 'T' + this.dueTime).toISOString();
        this.reminder.recipient_ids = this.selectedRecipientIds.length > 0 ? this.selectedRecipientIds : null;
        if (!this.reminder.recurrence) {
            this.reminder.recurrence = null;
        }

        const payload: Partial<Reminder> = {
            title: this.reminder.title,
            message: this.reminder.message,
            due_at: this.reminder.due_at,
            recurrence: this.reminder.recurrence,
            recipient_ids: this.reminder.recipient_ids,
        };

        if (this.isNew) {
            this.reminderService.createReminder(payload).subscribe(result => {
                this.dialogRef.close(result);
            });
        } else {
            this.reminderService.updateReminder(this.reminder.id, payload).subscribe(result => {
                this.dialogRef.close(result);
            });
        }
    }

    private toDateString(d: Date): string {
        return d.getFullYear() + '-' +
            String(d.getMonth() + 1).padStart(2, '0') + '-' +
            String(d.getDate()).padStart(2, '0');
    }

    private toTimeString(d: Date): string {
        return String(d.getHours()).padStart(2, '0') + ':' +
            String(d.getMinutes()).padStart(2, '0');
    }
}
