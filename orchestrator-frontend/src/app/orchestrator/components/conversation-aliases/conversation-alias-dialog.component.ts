import {Component, Inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatCheckboxModule} from '@angular/material/checkbox';
import {
    MAT_DIALOG_DATA,
    MatDialogModule,
    MatDialogRef,
} from '@angular/material/dialog';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {User} from '../../../users/user.model';
import {
    ConversationAlias,
    CreateConversationAlias,
    UpdateConversationAlias,
} from '../../models/conversation-alias.model';
import {ConversationAliasService} from '../../services/conversation-alias.service';

interface ConversationAliasDialogData {
    conversation: ConversationAlias | null;
    users: User[];
}

const ALIAS_PATTERN = /^[a-z][a-z0-9_-]{0,9}\/[a-z0-9][a-z0-9_-]{0,17}$/;
const SERVICE_PATTERN = /^[a-z][a-z0-9_-]{0,9}$/;

@Component({
    selector: 'app-conversation-alias-dialog',
    standalone: true,
    imports: [
        FormsModule,
        MatButtonModule,
        MatCheckboxModule,
        MatDialogModule,
        MatFormFieldModule,
        MatInputModule,
        MatSelectModule,
    ],
    templateUrl: './conversation-alias-dialog.component.html',
    styleUrl: './conversation-alias-dialog.component.scss',
})
export class ConversationAliasDialogComponent {
    readonly isNew: boolean;
    readonly services = [
        {value: 'tg', label: 'Telegram'},
        {value: 'fb', label: 'Messenger'},
        {value: 'rns', label: 'Reticulum'},
    ];
    saving = false;
    error = '';
    form: CreateConversationAlias;

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: ConversationAliasDialogData,
        private service: ConversationAliasService,
        private dialogRef: MatDialogRef<ConversationAliasDialogComponent>,
    ) {
        this.isNew = !data.conversation;
        const conversation = data.conversation;
        this.form = conversation ? {
            owner_user_id: conversation.owner_user_id,
            service: conversation.service,
            integration_account: conversation.integration_account,
            external_chat_id: conversation.external_chat_id,
            alias: conversation.alias,
            display_name: conversation.display_name,
            available: conversation.available,
        } : {
            owner_user_id: data.users[0]?.id ?? 0,
            service: 'tg',
            integration_account: 'telegram-main',
            external_chat_id: '',
            alias: 'tg/',
            display_name: '',
            available: true,
        };
    }

    serviceChanged(): void {
        this.form.service = this.form.service.trim().toLowerCase();
        const accounts: Record<string, string> = {
            tg: 'telegram-main',
            fb: 'messenger-main',
            rns: 'reticulum-main',
        };
        this.form.integration_account = accounts[this.form.service] ?? `${this.form.service}-main`;
        const suffix = this.form.alias.includes('/')
            ? this.form.alias.split('/', 2)[1]
            : this.form.alias;
        this.form.alias = `${this.form.service}/${suffix}`;
    }

    normalizeAlias(): void {
        let value = this.form.alias.trim().toLowerCase();
        if (value && !value.includes('/')) value = `${this.form.service}/${value}`;
        this.form.alias = value;
    }

    get validationError(): string {
        if (!this.form.owner_user_id) return 'Choose an owner.';
        if (!SERVICE_PATTERN.test(this.form.service.trim().toLowerCase())) {
            return 'Enter a channel prefix using up to 10 letters, numbers, _ or -.';
        }
        if (!this.form.integration_account.trim()) return 'Enter the integration account.';
        if (!this.form.external_chat_id.trim()) return 'Enter the external conversation ID.';
        if (!this.form.display_name.trim()) return 'Enter a display name.';
        const alias = this.form.alias.trim().toLowerCase();
        if (!ALIAS_PATTERN.test(alias)) return 'Enter an alias such as tg/family.';
        if (alias.split('/', 1)[0] !== this.form.service) {
            return `The alias must begin with ${this.form.service}/.`;
        }
        return '';
    }

    save(): void {
        this.normalizeAlias();
        if (this.validationError || this.saving) return;
        this.saving = true;
        this.error = '';
        const request = this.data.conversation
            ? this.service.update(this.data.conversation.id, {
                alias: this.form.alias,
                display_name: this.form.display_name.trim(),
                available: this.form.available,
            } satisfies UpdateConversationAlias)
            : this.service.create({
                ...this.form,
                service: this.form.service.trim().toLowerCase(),
                integration_account: this.form.integration_account.trim(),
                external_chat_id: this.form.external_chat_id.trim(),
                display_name: this.form.display_name.trim(),
            });
        request.subscribe({
            next: result => this.dialogRef.close(result),
            error: response => {
                this.error = response?.error?.message ?? 'Could not save the conversation.';
                this.saving = false;
            },
        });
    }
}
