import {Component, inject, OnInit} from '@angular/core';
import {NgFor, NgIf} from '@angular/common';
import {MatButton} from '@angular/material/button';
import {MatCard, MatCardActions, MatCardContent, MatCardHeader, MatCardTitle} from '@angular/material/card';
import {MatCheckbox} from '@angular/material/checkbox';
import {MatDialog} from '@angular/material/dialog';
import {MatSlideToggle} from '@angular/material/slide-toggle';
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
import {forkJoin} from 'rxjs';
import {MessageRelayEndpoint, MessageRelayRoute} from '../../models/telegram-relay.model';
import {TelegramRelayService} from '../../services/telegram-relay.service';
import {DestinationDialogComponent} from './destination-dialog/destination-dialog.component';
import {RuleDialogComponent} from './rule-dialog/rule-dialog.component';
import {ConfirmDialogComponent} from '../confirm-dialog/confirm-dialog.component';

@Component({
    selector: 'app-telegram-relay',
    standalone: true,
    imports: [
        NgFor,
        NgIf,
        MatButton,
        MatCard,
        MatCardActions,
        MatCardContent,
        MatCardHeader,
        MatCardTitle,
        MatCheckbox,
        MatSlideToggle,
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
    ],
    templateUrl: './telegram-relay.component.html',
    styleUrl: './telegram-relay.component.css'
})
export class TelegramRelayComponent implements OnInit {
    endpoints: MessageRelayEndpoint[] = [];
    routes: MessageRelayRoute[] = [];
    loading = false;
    error = '';
    runtimeWarning = '';
    readonly dialog = inject(MatDialog);
    endpointColumns: string[] = ['name', 'key', 'type', 'enabled', 'actions'];

    constructor(private relayService: TelegramRelayService) {}

    ngOnInit() {
        this.load();
    }

    load() {
        this.loading = true;
        this.error = '';
        forkJoin({
            endpoints: this.relayService.getEndpoints(),
            routes: this.relayService.getMessageRoutes(),
        }).subscribe({
            next: result => {
                this.endpoints = result.endpoints;
                this.routes = result.routes;
                this.loading = false;
            },
            error: error => {
                this.error = error?.error?.message ?? 'Could not load message routes.';
                this.loading = false;
            },
        });
    }

    sourceLabel(route: MessageRelayRoute): string {
        if (route.match_all_sources) return 'Everything';
        return route.sources.map(source => source.name).join(', ') || 'No source';
    }

    setRouteEnabled(route: MessageRelayRoute, enabled: boolean) {
        this.relayService.setMessageRouteEnabled(route.key, enabled).subscribe({
            next: result => {
                this.checkActivation(result);
                this.load();
            },
            error: () => this.load(),
        });
    }

    setTargetEnabled(route: MessageRelayRoute, endpoint: MessageRelayEndpoint, enabled: boolean) {
        this.relayService.setMessageRouteTargetEnabled(route.key, endpoint.key, enabled).subscribe({
            next: result => {
                this.checkActivation(result);
                this.load();
            },
            error: () => this.load(),
        });
    }

    private checkActivation(result: {runtime_applied?: boolean}) {
        this.runtimeWarning = result.runtime_applied === false
            ? 'Saved, but the running connector did not accept the update. Check its service status.'
            : '';
    }

    addEndpoint() {
        const ref = this.dialog.open(DestinationDialogComponent, {
            data: null, width: '760px', maxWidth: '90vw'
        });
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    editEndpoint(endpoint: MessageRelayEndpoint) {
        const ref = this.dialog.open(DestinationDialogComponent, {
            data: endpoint, width: '760px', maxWidth: '90vw'
        });
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    confirmDeleteEndpoint(endpoint: MessageRelayEndpoint) {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {message: `Delete endpoint "${endpoint.name}"? It will be removed from every route.`},
            width: '500px', maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) {
                this.relayService.deleteEndpoint(endpoint.id).subscribe(() => this.load());
            }
        });
    }

    addRoute() {
        const ref = this.dialog.open(RuleDialogComponent, {
            data: {route: null, endpoints: this.endpoints}, width: '900px', maxWidth: '90vw'
        });
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    editRoute(route: MessageRelayRoute) {
        const ref = this.dialog.open(RuleDialogComponent, {
            data: {route, endpoints: this.endpoints}, width: '900px', maxWidth: '90vw'
        });
        ref.afterClosed().subscribe(result => { if (result) this.load(); });
    }

    confirmDeleteRoute(route: MessageRelayRoute) {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {message: `Delete route "${route.name}"?`},
            width: '500px', maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) {
                this.relayService.deleteMessageRoute(route.id).subscribe(() => this.load());
            }
        });
    }
}
