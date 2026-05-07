import {Component, inject, OnInit} from '@angular/core';
import {NotificationSetting} from '../../../../orchestrator/models/reminder';
import {ReminderService} from '../../../../orchestrator/services/reminder.service';
import {MatButton} from '@angular/material/button';
import {MatCard, MatCardContent, MatCardHeader, MatCardTitle} from '@angular/material/card';
import {MatFormField, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {FormsModule} from '@angular/forms';
import {NgForOf, NgIf} from '@angular/common';
import {MatSlideToggleModule} from '@angular/material/slide-toggle';
import {MatSelectModule} from '@angular/material/select';
import {MatDialog} from '@angular/material/dialog';
import {ConfirmDialogComponent} from '../../../../orchestrator/components/confirm-dialog/confirm-dialog.component';
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
import {MatChip} from '@angular/material/chips';
import {MatIcon} from '@angular/material/icon';

interface ChannelDefinition {
    channel: string;
    label: string;
    fields: { key: string; label: string; placeholder: string; type: string }[];
}

const CHANNEL_DEFINITIONS: ChannelDefinition[] = [
    {
        channel: 'sms',
        label: 'SMS',
        fields: [{key: 'phone_number', label: 'Phone Number', placeholder: '+47...', type: 'tel'}],
    },
    {
        channel: 'telegram',
        label: 'Telegram',
        fields: [{key: 'chat_id', label: 'Chat ID', placeholder: 'Telegram chat ID', type: 'text'}],
    },
    {
        channel: 'teams',
        label: 'Microsoft Teams',
        fields: [{key: 'webhook_url', label: 'Webhook URL', placeholder: 'https://...webhook.office.com/...', type: 'url'}],
    },
];

@Component({
    selector: 'app-notification-settings',
    standalone: true,
    imports: [
        MatButton,
        MatCard,
        MatCardContent,
        MatCardHeader,
        MatCardTitle,
        MatFormField,
        MatInput,
        MatLabel,
        FormsModule,
        NgForOf,
        NgIf,
        MatSlideToggleModule,
        MatSelectModule,
        MatTable,
        MatColumnDef,
        MatHeaderCell,
        MatHeaderCellDef,
        MatCell,
        MatCellDef,
        MatHeaderRow,
        MatHeaderRowDef,
        MatRow,
        MatRowDef,
        MatChip,
        MatIcon,
    ],
    templateUrl: './notification-settings.component.html',
    styleUrl: './notification-settings.component.scss'
})
export class NotificationSettingsComponent implements OnInit {
    settings: NotificationSetting[] = [];
    displayedColumns: string[] = ['channel', 'user_label', 'config', 'enabled', 'actions'];

    channelDefinitions = CHANNEL_DEFINITIONS;
    newChannel: string = 'sms';
    newUserLabel: string = '';
    newConfig: Record<string, any> = {};

    readonly dialog = inject(MatDialog);

    constructor(private reminderService: ReminderService) {
    }

    ngOnInit() {
        this.loadSettings();
    }

    get selectedChannelDef(): ChannelDefinition {
        return this.channelDefinitions.find(c => c.channel === this.newChannel) || this.channelDefinitions[0];
    }

    loadSettings() {
        this.reminderService.getNotificationSettings().subscribe(settings => {
            this.settings = settings;
        });
    }

    getChannelLabel(channel: string): string {
        return this.channelDefinitions.find(c => c.channel === channel)?.label || channel;
    }

    configSummary(setting: NotificationSetting): string {
        const c = setting.config;
        if (setting.channel === 'sms') return c['phone_number'] || '';
        if (setting.channel === 'telegram') return c['chat_id'] ? `chat ${c['chat_id']}` : '';
        if (setting.channel === 'teams') return c['webhook_url'] ? 'Webhook configured' : '';
        return JSON.stringify(c);
    }

    toggleEnabled(setting: NotificationSetting) {
        setting.enabled = !setting.enabled;
        this.reminderService.updateNotificationSettings([{
            channel: setting.channel,
            enabled: setting.enabled,
            config: setting.config,
            user_label: setting.user_label,
        }]).subscribe(() => this.loadSettings());
    }

    confirmDelete(setting: NotificationSetting) {
        const label = setting.user_label || 'System';
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            data: {
                title: 'Remove channel?',
                message: `Delete ${this.getChannelLabel(setting.channel)} for "${label}"?`,
                confirmLabel: 'Delete',
            },
            width: '500px',
            maxWidth: '90vw',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.reminderService.deleteNotificationSetting(setting.id).subscribe(() => {
                    this.loadSettings();
                });
            }
        });
    }

    addChannel() {
        this.reminderService.updateNotificationSettings([{
            channel: this.newChannel,
            enabled: true,
            config: {...this.newConfig},
            user_label: this.newUserLabel,
        }]).subscribe(() => {
            this.newConfig = {};
            this.newUserLabel = '';
            this.loadSettings();
        });
    }
}
