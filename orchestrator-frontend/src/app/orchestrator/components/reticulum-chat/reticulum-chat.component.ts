import {CommonModule} from '@angular/common';
import {
    AfterViewChecked,
    Component,
    ElementRef,
    OnDestroy,
    OnInit,
    ViewChild,
} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatIconModule} from '@angular/material/icon';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {
    ReticulumAnnounce,
    ReticulumConversation,
    ReticulumMessage,
    ReticulumStatus,
} from '../../models/reticulum-chat.model';
import {ReticulumChatService} from '../../services/reticulum-chat.service';
import {ReticulumAnnounceStreamComponent} from './reticulum-announce-stream.component';

@Component({
    selector: 'app-reticulum-chat',
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatIconModule,
        MatInputModule,
        MatSelectModule,
        ReticulumAnnounceStreamComponent,
    ],
    templateUrl: './reticulum-chat.component.html',
    styleUrl: './reticulum-chat.component.scss',
})
export class ReticulumChatComponent implements OnInit, OnDestroy, AfterViewChecked {
    @ViewChild('messageList') private messageList?: ElementRef<HTMLElement>;

    status: ReticulumStatus | null = null;
    conversations: ReticulumConversation[] = [];
    messages: ReticulumMessage[] = [];
    activeHash = '';
    activeName = '';
    destinationHash = '';
    draft = '';
    deliveryMethod: 'direct' | 'opportunistic' | 'propagated' = 'direct';
    loading = true;
    sending = false;
    error = '';
    view: 'chat' | 'announces' = 'chat';
    private pollTimer?: number;
    private shouldScroll = false;

    constructor(private chat: ReticulumChatService) {}

    ngOnInit(): void {
        this.refreshStatus();
        this.chat.conversations().subscribe({
            next: conversations => {
                this.acceptConversations(conversations);
                this.loading = false;
            },
            error: error => {
                this.error = this.errorMessage(error, 'Could not connect to the Reticulum relay.');
                this.loading = false;
            },
        });
        this.pollTimer = window.setInterval(() => this.poll(), 3000);
    }

    ngOnDestroy(): void {
        if (this.pollTimer !== undefined) window.clearInterval(this.pollTimer);
    }

    ngAfterViewChecked(): void {
        if (this.shouldScroll && this.messageList) {
            this.messageList.nativeElement.scrollTop = this.messageList.nativeElement.scrollHeight;
            this.shouldScroll = false;
        }
    }

    selectConversation(conversation: ReticulumConversation): void {
        this.openConversation(conversation.destination_hash, conversation.display_name);
    }

    openFromAnnounce(announce: ReticulumAnnounce): void {
        this.view = 'chat';
        this.openConversation(announce.destination_hash, announce.display_name || '');
    }

    startConversation(): void {
        const destination = this.destinationHash.trim().toLowerCase();
        if (!/^[0-9a-f]{32}$/.test(destination)) {
            this.error = 'Enter a 32-character hexadecimal LXMF destination hash.';
            return;
        }
        this.destinationHash = '';
        const known = this.conversations.find(item => item.destination_hash === destination);
        this.openConversation(destination, known?.display_name || '');
    }

    send(): void {
        const text = this.draft.trim();
        if (!text || !this.activeHash || this.sending) return;
        this.sending = true;
        this.error = '';
        this.chat.send({
            destination_hash: this.activeHash,
            text,
            delivery_method: this.deliveryMethod,
            client_token: crypto.randomUUID(),
        }).subscribe({
            next: message => {
                this.draft = '';
                this.sending = false;
                if (!this.messages.some(item => item.message_hash === message.message_hash)) {
                    this.messages = [...this.messages, message];
                }
                this.shouldScroll = true;
                this.refreshConversations();
            },
            error: error => {
                this.error = this.errorMessage(error, 'Could not send the LXMF message.');
                this.sending = false;
            },
        });
    }

    sendOnEnter(event: Event): void {
        const keyboardEvent = event as KeyboardEvent;
        if (keyboardEvent.shiftKey) return;
        keyboardEvent.preventDefault();
        this.send();
    }

    timestamp(seconds: number): Date {
        return new Date(seconds * 1000);
    }

    trackConversation(_: number, conversation: ReticulumConversation): string {
        return conversation.destination_hash;
    }

    trackMessage(_: number, message: ReticulumMessage): string {
        return message.message_hash;
    }

    private openConversation(destinationHash: string, displayName = ''): void {
        this.activeHash = destinationHash;
        this.activeName = displayName;
        this.messages = [];
        this.error = '';
        this.loadMessages(true);
        this.chat.markRead(destinationHash).subscribe({error: () => undefined});
        this.conversations = this.conversations.map(item =>
            item.destination_hash === destinationHash ? {...item, unread_count: 0} : item,
        );
    }

    private poll(): void {
        this.refreshStatus();
        this.refreshConversations();
        if (this.activeHash) this.loadMessages(false);
    }

    private refreshStatus(): void {
        this.chat.status().subscribe({
            next: status => this.status = status,
            error: error => {
                const status = error?.error as ReticulumStatus | undefined;
                this.status = status?.status ? status : null;
            },
        });
    }

    private refreshConversations(): void {
        this.chat.conversations().subscribe({
            next: conversations => this.acceptConversations(conversations),
            error: () => undefined,
        });
    }

    private acceptConversations(conversations: ReticulumConversation[]): void {
        const active = conversations.find(item => item.destination_hash === this.activeHash);
        if (active?.display_name) this.activeName = active.display_name;
        if (active?.unread_count) {
            this.chat.markRead(this.activeHash).subscribe({error: () => undefined});
            conversations = conversations.map(item =>
                item.destination_hash === this.activeHash ? {...item, unread_count: 0} : item,
            );
        }
        this.conversations = conversations;
        if (!this.activeHash && conversations.length) {
            this.openConversation(
                conversations[0].destination_hash,
                conversations[0].display_name,
            );
        }
    }

    private loadMessages(scroll: boolean): void {
        const requestedHash = this.activeHash;
        this.chat.messages(requestedHash).subscribe({
            next: messages => {
                if (requestedHash !== this.activeHash) return;
                const lastHash = this.messages.at(-1)?.message_hash;
                this.messages = messages;
                if (scroll || messages.at(-1)?.message_hash !== lastHash) this.shouldScroll = true;
            },
            error: error => {
                if (requestedHash === this.activeHash) {
                    this.error = this.errorMessage(error, 'Could not load this conversation.');
                }
            },
        });
    }

    private errorMessage(error: {error?: {message?: string}}, fallback: string): string {
        return error?.error?.message || fallback;
    }
}
