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
import {NgFor, NgIf} from '@angular/common';
import {
    MessageRelayEndpoint,
    MessageRelayRoute,
    MessageRelayRouteWrite,
} from '../../../models/telegram-relay.model';
import {TelegramRelayService} from '../../../services/telegram-relay.service';

export interface RouteDialogData {
    route: MessageRelayRoute | null;
    endpoints: MessageRelayEndpoint[];
}

@Component({
    selector: 'app-rule-dialog',
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
        MatOption,
        MatSelect,
        FormsModule,
        NgFor,
        NgIf,
    ],
    templateUrl: './rule-dialog.component.html',
    styleUrl: './rule-dialog.component.css',
})
export class RuleDialogComponent {
    readonly sourceEndpoints: MessageRelayEndpoint[];
    readonly targetEndpoints: MessageRelayEndpoint[];
    route: MessageRelayRouteWrite;
    targetEndpointIds: number[] = [];
    filterJson = '';
    jsonError: string | null = null;
    isNew: boolean;

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: RouteDialogData,
        private relayService: TelegramRelayService,
        private dialogRef: MatDialogRef<RuleDialogComponent>,
    ) {
        const existing = data.route;
        this.isNew = !existing;
        this.sourceEndpoints = data.endpoints.filter(endpoint =>
            endpoint.capabilities.includes('source'));
        this.targetEndpoints = data.endpoints.filter(endpoint =>
            endpoint.capabilities.includes('target'));
        this.route = {
            id: existing?.id ?? 0,
            key: existing?.key ?? '',
            name: existing?.name ?? '',
            enabled: existing?.enabled ?? true,
            match_all_sources: existing?.match_all_sources ?? false,
            filter: existing?.filter ?? null,
            source_endpoint_ids: existing?.sources.map(source => source.id) ?? [],
            targets: existing?.targets.map(target => ({
                endpoint_id: target.endpoint.id,
                enabled: target.enabled,
                transform: target.transform,
            })) ?? [],
        };
        this.targetEndpointIds = this.route.targets.map(target => target.endpoint_id);
        this.filterJson = this.route.filter ? JSON.stringify(this.route.filter, null, 2) : '';
    }

    normalizeKey() {
        if (!this.isNew || this.route.key) return;
        this.route.key = this.route.name
            .toLowerCase()
            .trim()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
    }

    save() {
        this.jsonError = null;
        try {
            this.route.filter = this.filterJson.trim() ? JSON.parse(this.filterJson) : null;
        } catch (error: any) {
            this.jsonError = 'Invalid filter JSON: ' + error.message;
            return;
        }

        const existingTargets = new Map(
            this.route.targets.map(target => [target.endpoint_id, target])
        );
        this.route.targets = this.targetEndpointIds.map(endpointId =>
            existingTargets.get(endpointId) ?? {
                endpoint_id: endpointId,
                enabled: true,
                transform: {},
            }
        );
        this.relayService.saveMessageRoute(this.route).subscribe(result => {
            this.dialogRef.close(result);
        });
    }
}
