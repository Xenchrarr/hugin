import {Component, OnInit} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatCardModule} from '@angular/material/card';
import {MatDialog} from '@angular/material/dialog';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatIconModule} from '@angular/material/icon';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {MatTableModule} from '@angular/material/table';
import {forkJoin} from 'rxjs';
import {User} from '../../../users/user.model';
import {UserService} from '../../../users/user.service';
import {ConversationAlias} from '../../models/conversation-alias.model';
import {ConversationAliasService} from '../../services/conversation-alias.service';
import {ConversationAliasDialogComponent} from './conversation-alias-dialog.component';

@Component({
    selector: 'app-conversation-aliases',
    standalone: true,
    imports: [
        FormsModule,
        MatButtonModule,
        MatCardModule,
        MatFormFieldModule,
        MatIconModule,
        MatInputModule,
        MatSelectModule,
        MatTableModule,
    ],
    templateUrl: './conversation-aliases.component.html',
    styleUrl: './conversation-aliases.component.scss',
})
export class ConversationAliasesComponent implements OnInit {
    conversations: ConversationAlias[] = [];
    users: User[] = [];
    loading = false;
    error = '';
    query = '';
    channel = '';
    readonly columns = ['conversation', 'alias', 'channel', 'owner', 'external', 'status', 'actions'];

    constructor(
        private aliases: ConversationAliasService,
        private userService: UserService,
        private dialog: MatDialog,
    ) {}

    ngOnInit(): void {
        this.load();
    }

    load(): void {
        this.loading = true;
        this.error = '';
        forkJoin({aliases: this.aliases.list(), users: this.userService.list()}).subscribe({
            next: result => {
                this.conversations = result.aliases.conversations;
                this.users = result.users;
                this.loading = false;
            },
            error: response => {
                this.error = response?.error?.message ?? 'Could not load conversations.';
                this.loading = false;
            },
        });
    }

    get visibleConversations(): ConversationAlias[] {
        const query = this.query.trim().toLowerCase();
        return this.conversations.filter(item => {
            if (this.channel && item.service !== this.channel) return false;
            if (!query) return true;
            return [
                item.display_name,
                item.alias,
                item.service,
                item.integration_account,
                item.external_chat_id,
                this.ownerName(item.owner_user_id),
            ].some(value => value.toLowerCase().includes(query));
        });
    }

    get channelCount(): number {
        return new Set(this.conversations.map(item => item.service)).size;
    }

    get channels(): string[] {
        return [...new Set(this.conversations.map(item => item.service))].sort();
    }

    get unavailableCount(): number {
        return this.conversations.filter(item => !item.available).length;
    }

    ownerName(userId: number): string {
        const user = this.users.find(item => item.id === userId);
        return user?.display_name || user?.username || `User ${userId}`;
    }

    channelName(service: string): string {
        return {tg: 'Telegram', fb: 'Messenger', rns: 'Reticulum'}[service] ?? service;
    }

    add(): void {
        this.openDialog(null);
    }

    edit(conversation: ConversationAlias): void {
        this.openDialog(conversation);
    }

    private openDialog(conversation: ConversationAlias | null): void {
        const reference = this.dialog.open(ConversationAliasDialogComponent, {
            data: {conversation, users: this.users},
            width: '760px',
            maxWidth: '94vw',
        });
        reference.afterClosed().subscribe(result => {
            if (result) this.load();
        });
    }

    remove(conversation: ConversationAlias): void {
        if (!confirm(`Delete ${conversation.alias}? Its routed message history will also be removed.`)) {
            return;
        }
        this.aliases.delete(conversation.id).subscribe({
            next: () => this.load(),
            error: response => {
                this.error = response?.error?.message ?? 'Could not delete the conversation.';
            },
        });
    }
}
