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
import {MatFormField, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {MatOption, MatSelect} from '@angular/material/select';
import {FormsModule} from '@angular/forms';
import {NgIf} from '@angular/common';
import {TelegramRelayDestination} from '../../../models/telegram-relay.model';
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
    destination: TelegramRelayDestination;
    isNew = false;

    // convenience getters / setters so templates can bind to flat fields
    get webhookUrl(): string { return this.destination.config['url'] ?? ''; }
    set webhookUrl(v: string) { this.destination.config['url'] = v; }

    get webhookToken(): string { return (this.destination.config['headers'] ?? {})['Authorization']?.replace('Bearer ', '') ?? ''; }
    set webhookToken(v: string) {
        if (!this.destination.config['headers']) this.destination.config['headers'] = {};
        this.destination.config['headers']['Authorization'] = v ? `Bearer ${v}` : '';
    }

    get smsPhone(): string { return this.destination.config['phone'] ?? ''; }
    set smsPhone(v: string) { this.destination.config['phone'] = v; }

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: TelegramRelayDestination | null,
        private relayService: TelegramRelayService,
        private dialogRef: MatDialogRef<DestinationDialogComponent>,
    ) {
        if (!data) {
            this.destination = {id: 0, name: '', type: 'webhook', config: {}, enabled: true};
            this.isNew = true;
        } else {
            this.destination = {...data, config: {...(data.config || {})}};
        }
    }

    save() {
        this.relayService.saveDestination(this.destination).subscribe(result => {
            this.dialogRef.close(result);
        });
    }
}
