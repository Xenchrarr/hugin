import {Component, inject, OnInit} from '@angular/core';
import {TelegramRelayDestination, TelegramRelayRule} from '../../models/telegram-relay.model';
import {TelegramRelayService} from '../../services/telegram-relay.service';
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
import {MatCheckbox} from '@angular/material/checkbox';
import {NgIf} from '@angular/common';
import {MatDialog} from '@angular/material/dialog';
import {DestinationDialogComponent} from './destination-dialog/destination-dialog.component';
import {RuleDialogComponent} from './rule-dialog/rule-dialog.component';
import {ConfirmDialogComponent} from '../confirm-dialog/confirm-dialog.component';

@Component({
    selector: 'app-telegram-relay',
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
        MatCheckbox,
        NgIf,
    ],
    templateUrl: './telegram-relay.component.html',
    styleUrl: './telegram-relay.component.css'
})
export class TelegramRelayComponent implements OnInit {
    destinations: TelegramRelayDestination[] = [];
    rules: TelegramRelayRule[] = [];
    readonly dialog = inject(MatDialog);

    destinationColumns: string[] = ['id', 'name', 'type', 'enabled', 'actions'];
    ruleColumns: string[] = ['id', 'name', 'priority', 'enabled', 'continue_on_match', 'is_preset', 'actions'];

    constructor(private relayService: TelegramRelayService) {}

    ngOnInit() {
        this.load();
    }

    load() {
        this.relayService.getDestinations().subscribe(d => this.destinations = d);
        this.relayService.getRules().subscribe(r => this.rules = r);
    }

    // ── Destinations ────────────────────────────────────────

    addDestination() {
        const ref = this.dialog.open(DestinationDialogComponent, {data: null, width: '1000px', maxWidth: '90vw'});
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    editDestination(dest: TelegramRelayDestination) {
        const ref = this.dialog.open(DestinationDialogComponent, {data: dest, width: '1000px', maxWidth: '90vw'});
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    confirmDeleteDestination(dest: TelegramRelayDestination) {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {message: `Delete destination "${dest.name}"?`},
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) {
                this.relayService.deleteDestination(dest.id).subscribe(() => this.load());
            }
        });
    }

    // ── Rules ────────────────────────────────────────────────

    addRule() {
        const ref = this.dialog.open(RuleDialogComponent, {data: null, width: '1000px', maxWidth: '90vw'});
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    editRule(rule: TelegramRelayRule) {
        const ref = this.dialog.open(RuleDialogComponent, {data: rule, width: '1000px', maxWidth: '90vw'});
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    confirmDeleteRule(rule: TelegramRelayRule) {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {message: `Delete rule "${rule.name}"?`},
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) {
                this.relayService.deleteRule(rule.id).subscribe(() => this.load());
            }
        });
    }

    setPreset(enabled: boolean) {
        this.relayService.setPresetEnabled(enabled).subscribe(() => this.load());
    }
}
