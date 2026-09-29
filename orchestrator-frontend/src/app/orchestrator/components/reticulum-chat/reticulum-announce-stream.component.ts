import {CommonModule} from '@angular/common';
import {Component, EventEmitter, Input, OnDestroy, OnInit, Output} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatIconModule} from '@angular/material/icon';
import {MatSelectModule} from '@angular/material/select';
import {
    ReticulumAnnounce,
    ReticulumAnnounceTarget,
    ReticulumStatus,
} from '../../models/reticulum-chat.model';
import {ReticulumChatService} from '../../services/reticulum-chat.service';

@Component({
    selector: 'app-reticulum-announce-stream',
    standalone: true,
    imports: [
        CommonModule,
        FormsModule,
        MatButtonModule,
        MatFormFieldModule,
        MatIconModule,
        MatSelectModule,
    ],
    templateUrl: './reticulum-announce-stream.component.html',
    styleUrl: './reticulum-announce-stream.component.scss',
})
export class ReticulumAnnounceStreamComponent implements OnInit, OnDestroy {
    @Input() status: ReticulumStatus | null = null;
    @Output() messageDestination = new EventEmitter<ReticulumAnnounce>();

    announces: ReticulumAnnounce[] = [];
    aspect = '';
    announceTarget: ReticulumAnnounceTarget = 'delivery';
    loading = true;
    announcing = false;
    error = '';
    notice = '';
    private pollTimer?: number;

    constructor(private chat: ReticulumChatService) {}

    ngOnInit(): void {
        this.load();
        this.pollTimer = window.setInterval(() => this.load(true), 3000);
    }

    ngOnDestroy(): void {
        if (this.pollTimer !== undefined) window.clearInterval(this.pollTimer);
    }

    load(silent = false): void {
        if (!silent) this.loading = true;
        this.chat.announces(200, this.aspect).subscribe({
            next: announces => {
                this.announces = announces;
                this.loading = false;
            },
            error: error => {
                if (!silent) this.error = this.errorMessage(error, 'Could not load announces.');
                this.loading = false;
            },
        });
    }

    sendAnnounce(): void {
        if (!this.status?.ready || this.announcing) return;
        this.announcing = true;
        this.error = '';
        this.notice = '';
        this.chat.announce(this.announceTarget).subscribe({
            next: result => {
                const targets = result.targets.map(item => this.targetLabel(item.target)).join(', ');
                this.notice = `Announce sent for ${targets}.`;
                this.announcing = false;
            },
            error: error => {
                this.error = this.errorMessage(error, 'Could not send the announce.');
                this.announcing = false;
            },
        });
    }

    timestamp(seconds: number): Date {
        return new Date(seconds * 1000);
    }

    label(item: ReticulumAnnounce): string {
        return item.display_name || item.destination_hash.slice(0, 12);
    }

    aspectLabel(aspect: ReticulumAnnounce['aspect']): string {
        return {
            'lxmf.delivery': 'LXMF peer',
            'lxmf.propagation': 'Propagation node',
            'nomadnetwork.node': 'NomadNet site',
            'unknown': 'Other',
        }[aspect];
    }

    icon(aspect: ReticulumAnnounce['aspect']): string {
        return {
            'lxmf.delivery': 'person',
            'lxmf.propagation': 'dns',
            'nomadnetwork.node': 'language',
            'unknown': 'cell_tower',
        }[aspect];
    }

    trackAnnounce(_: number, item: ReticulumAnnounce): string {
        return item.destination_hash;
    }

    private targetLabel(target: string): string {
        return {
            delivery: 'LXMF identity',
            site: 'NomadNet site',
            propagation: 'propagation node',
        }[target] || target;
    }

    private errorMessage(error: {error?: {message?: string}}, fallback: string): string {
        return error?.error?.message || fallback;
    }
}
