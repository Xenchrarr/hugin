import {Component, Inject} from '@angular/core';
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
import {MatFormField, MatHint, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {MatOption, MatSelect} from '@angular/material/select';
import {FormsModule} from '@angular/forms';
import {NgIf} from '@angular/common';
import {MessageRelayEndpoint} from '../../../models/telegram-relay.model';
import {TelegramRelayService} from '../../../services/telegram-relay.service';

@Component({
    selector: 'app-destination-dialog',
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
        MatHint,
        MatInput,
        MatLabel,
        MatSelect,
        MatOption,
        FormsModule,
        NgIf,
    ],
    templateUrl: './destination-dialog.component.html',
})
export class DestinationDialogComponent {
    endpoint: MessageRelayEndpoint;
    isNew = false;

    get webhookUrl(): string { return this.endpoint.config['url'] ?? ''; }
    set webhookUrl(v: string) { this.endpoint.config['url'] = v; }

    get webhookToken(): string {
        return (this.endpoint.config['headers'] ?? {})['Authorization']?.replace('Bearer ', '') ?? '';
    }
    set webhookToken(v: string) {
        if (!this.endpoint.config['headers']) this.endpoint.config['headers'] = {};
        this.endpoint.config['headers']['Authorization'] = v ? `Bearer ${v}` : '';
    }

    get smsPhone(): string { return this.endpoint.config['phone'] ?? ''; }
    set smsPhone(v: string) { this.endpoint.config['phone'] = v; }

    get smsRecoveryPolicy(): string {
        return this.endpoint.config['recovery_policy'] ?? 'digest_hold';
    }
    set smsRecoveryPolicy(v: string) {
        this.endpoint.config['recovery_policy'] = v;
    }

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: MessageRelayEndpoint | null,
        private relayService: TelegramRelayService,
        private dialogRef: MatDialogRef<DestinationDialogComponent>,
    ) {
        if (!data) {
            this.endpoint = {
                id: 0,
                key: '',
                name: '',
                type: 'sms',
                enabled: true,
                capabilities: ['target'],
                config: {},
            };
            this.isNew = true;
        } else {
            this.endpoint = {...data, config: {...(data.config || {})}};
        }
    }

    normalizeKey() {
        if (!this.isNew || this.endpoint.key) return;
        this.endpoint.key = this.endpoint.name
            .toLowerCase()
            .trim()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
    }

    save() {
        this.endpoint.capabilities = this.endpoint.type === 'telegram'
            ? ['source']
            : ['target'];
        this.relayService.saveEndpoint(this.endpoint).subscribe(result => {
            this.dialogRef.close(result);
        });
    }
}
