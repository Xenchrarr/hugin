import {DatePipe, NgFor, NgIf} from '@angular/common';
import {Component, inject, OnInit} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButton} from '@angular/material/button';
import {MatCard, MatCardContent, MatCardHeader, MatCardTitle} from '@angular/material/card';
import {MatCheckbox} from '@angular/material/checkbox';
import {MatDialog} from '@angular/material/dialog';
import {MatFormField, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {MatPaginator, PageEvent} from '@angular/material/paginator';
import {MatOption, MatSelect} from '@angular/material/select';
import {
    MatCell, MatCellDef, MatColumnDef, MatHeaderCell, MatHeaderCellDef,
    MatHeaderRow, MatHeaderRowDef, MatRow, MatRowDef, MatTable,
} from '@angular/material/table';
import {forkJoin, Observable} from 'rxjs';
import {
    MessageHubBulkAction,
    MessageHubBulkOperation,
    MessageHubDelivery,
    MessageHubDeliveryFilters,
    MessageHubDeliveryGroup,
    MessageHubDeliveryGroupPage,
    MessageHubDeliveryPage,
    MessageHubGatewayStats,
    MessageHubQueueBucket,
    MessageHubStats,
} from '../../models/message-hub.model';
import {MessageHubService} from '../../services/message-hub.service';
import {ConfirmDialogComponent} from '../confirm-dialog/confirm-dialog.component';
import {
    DeliveryDetailsDialogComponent,
    DeliveryDetailsDialogResult,
} from './delivery-details-dialog.component';

@Component({
    selector: 'app-message-hub',
    standalone: true,
    imports: [
        DatePipe, FormsModule, NgFor, NgIf, MatButton, MatCard, MatCardContent,
        MatCardHeader, MatCardTitle, MatCheckbox, MatCell, MatCellDef, MatColumnDef,
        MatFormField, MatHeaderCell, MatHeaderCellDef, MatHeaderRow, MatHeaderRowDef,
        MatInput, MatLabel, MatOption, MatPaginator, MatRow, MatRowDef, MatSelect, MatTable,
    ],
    templateUrl: './message-hub.component.html',
    styleUrl: './message-hub.component.scss',
})
export class MessageHubComponent implements OnInit {
    stats: MessageHubStats = {
        gateways: [],
        open_incidents: [],
        attachments: {count: 0, size_bytes: 0},
    };
    deliveries: MessageHubDelivery[] = [];
    groups: MessageHubDeliveryGroup[] = [];
    bulkOperations: MessageHubBulkOperation[] = [];
    loading = false;
    error = '';
    notice = '';
    busy = new Set<number>();
    bulkBusy = false;
    bulkProgressUpdated = 0;
    bulkProgressTotal = 0;
    operationBusy = new Set<number>();
    selected = new Set<number>();
    allMatchingSelected = false;
    expanded = new Set<number>();
    view: 'held' | 'all' = 'held';
    layout: 'messages' | 'groups' = 'groups';
    searchText = '';
    recipientFilter = '';
    gatewayFilter = '';
    ageFilter = '';
    sortOrder: 'asc' | 'desc' = 'desc';
    sourceTypeFilter = '';
    sourceLabelFilter = '';
    private appliedSearchText = '';
    private appliedRecipientFilter = '';
    private appliedGatewayFilter = '';
    private appliedAgeFilter = '';
    private appliedCreatedAfter: string | undefined;
    private appliedSortOrder: 'asc' | 'desc' = 'desc';
    private appliedCreatedBefore = new Date().toISOString();
    private appliedSourceTypeFilter = '';
    private appliedSourceLabelFilter = '';
    expandedGroups = new Set<string>();
    groupMessages = new Map<string, MessageHubDelivery[]>();
    groupLoading = new Set<string>();
    pageIndex = 0;
    pageSize = 25;
    totalItems = 0;
    readonly maxBulkSelection = 500;
    readonly actionableStatuses = ['uncertain', 'dead', 'held', 'retry_wait', 'pending'];
    readonly dialog = inject(MatDialog);
    readonly columns = [
        'select', 'created', 'source', 'gateway', 'recipient', 'status', 'message', 'attempts',
        'actions',
    ];

    constructor(private hub: MessageHubService) {}

    ngOnInit(): void {
        this.load();
    }

    load(): void {
        this.loading = true;
        this.error = '';
        forkJoin({
            stats: this.hub.getStats(),
            page: this.layout === 'groups' ? this.groupRequest() : this.deliveryRequest(),
            operations: this.hub.getBulkOperations(),
        }).subscribe({
            next: result => {
                this.stats = result.stats;
                this.bulkOperations = result.operations;
                this.acceptResultPage(result.page);
                this.clearSelection();
                this.loading = false;
            },
            error: error => {
                this.error = error?.error?.message ?? 'Could not load Message Hub status.';
                this.loading = false;
            },
        });
    }

    private deliveryFilters(): MessageHubDeliveryFilters {
        return {
            statuses: this.view === 'held' ? ['held'] : this.actionableStatuses,
            gatewayKey: this.appliedGatewayFilter || undefined,
            recipient: this.appliedRecipientFilter || undefined,
            query: this.appliedSearchText || undefined,
            createdAfter: this.appliedCreatedAfter,
            createdBefore: this.appliedCreatedBefore,
            sort: this.appliedSortOrder,
            sourceType: this.appliedSourceTypeFilter || undefined,
            sourceLabel: this.appliedSourceLabelFilter || undefined,
            page: this.pageIndex + 1,
            pageSize: this.pageSize,
        };
    }

    private deliveryRequest() {
        return this.hub.searchDeliveries(this.deliveryFilters());
    }

    private groupRequest() {
        return this.hub.searchDeliveryGroups(this.deliveryFilters());
    }

    private acceptResultPage(page: MessageHubDeliveryPage | MessageHubDeliveryGroupPage): void {
        if (this.layout === 'groups') {
            this.groups = (page as MessageHubDeliveryGroupPage).items;
            this.deliveries = [];
        } else {
            this.deliveries = (page as MessageHubDeliveryPage).items;
            this.groups = [];
        }
        this.totalItems = page.total;
    }

    loadDeliveries(): void {
        this.loading = true;
        this.error = '';
        const request = (
            this.layout === 'groups' ? this.groupRequest() : this.deliveryRequest()
        ) as Observable<MessageHubDeliveryPage | MessageHubDeliveryGroupPage>;
        request.subscribe({
            next: result => {
                this.acceptResultPage(result);
                this.clearSelection();
                this.loading = false;
            },
            error: error => {
                this.error = error?.error?.message ?? 'Could not load Message Hub deliveries.';
                this.loading = false;
            },
        });
    }

    get heldCount(): number {
        return this.stats.gateways.reduce(
            (total, gateway) => total + (gateway.deliveries['held']?.count ?? 0),
            0,
        );
    }

    get actionableCount(): number {
        return this.stats.gateways.reduce(
            (total, gateway) => total + this.actionableStatuses.reduce(
                (gatewayTotal, status) => gatewayTotal + (gateway.deliveries[status]?.count ?? 0),
                0,
            ),
            0,
        );
    }

    get visibleDeliveries(): MessageHubDelivery[] {
        return this.deliveries;
    }

    get selectedDeliveries(): MessageHubDelivery[] {
        return this.deliveries.filter(item => this.selected.has(item.id));
    }

    get selectionCount(): number {
        return this.allMatchingSelected ? this.totalItems : this.selected.size;
    }

    clearSelection(): void {
        this.selected.clear();
        this.allMatchingSelected = false;
    }

    setView(view: 'held' | 'all'): void {
        this.view = view;
        if (view === 'all') this.layout = 'messages';
        this.pageIndex = 0;
        this.clearSelection();
        this.loadDeliveries();
    }

    setLayout(layout: 'messages' | 'groups'): void {
        this.layout = layout;
        this.pageIndex = 0;
        this.clearSelection();
        this.expandedGroups.clear();
        this.loadDeliveries();
    }

    applyFilters(): void {
        this.clearSelection();
        this.appliedSearchText = this.searchText.trim();
        this.appliedRecipientFilter = this.recipientFilter.trim();
        this.appliedGatewayFilter = this.gatewayFilter;
        this.appliedAgeFilter = this.ageFilter;
        this.appliedCreatedAfter = this.createdAfterForAge(this.appliedAgeFilter);
        this.appliedSortOrder = this.sortOrder;
        this.appliedSourceTypeFilter = this.sourceTypeFilter.trim();
        this.appliedSourceLabelFilter = this.sourceLabelFilter.trim();
        this.appliedCreatedBefore = new Date().toISOString();
        this.pageIndex = 0;
        this.loadDeliveries();
    }

    reload(): void {
        this.clearSelection();
        this.appliedCreatedAfter = this.createdAfterForAge(this.appliedAgeFilter);
        this.appliedCreatedBefore = new Date().toISOString();
        this.load();
    }

    private createdAfterForAge(age: string): string | undefined {
        if (!age) return undefined;
        const date = new Date();
        date.setDate(date.getDate() - Number(age));
        return date.toISOString();
    }

    clearFilters(): void {
        this.searchText = '';
        this.recipientFilter = '';
        this.gatewayFilter = '';
        this.ageFilter = '';
        this.sortOrder = 'desc';
        this.sourceTypeFilter = '';
        this.sourceLabelFilter = '';
        this.applyFilters();
    }

    pageChanged(event: PageEvent): void {
        this.pageIndex = event.pageIndex;
        this.pageSize = event.pageSize;
        this.loadDeliveries();
    }

    groupKey(group: MessageHubDeliveryGroup): string {
        return [
            group.gateway_key, group.recipient_key, group.source_type,
            group.source_label, group.conversation_key ?? '',
        ].join('\u0000');
    }

    toggleGroup(group: MessageHubDeliveryGroup): void {
        const key = this.groupKey(group);
        if (this.expandedGroups.has(key)) {
            this.expandedGroups.delete(key);
            return;
        }
        this.expandedGroups.add(key);
        if (this.groupMessages.has(key)) return;
        this.groupLoading.add(key);
        this.hub.searchDeliveries({
            ...this.deliveryFilters(),
            gatewayKey: group.gateway_key,
            recipient: group.recipient_key,
            sourceType: group.source_type,
            sourceLabel: undefined,
            sourceLabelExact: group.source_label,
            conversationKey: group.conversation_key ?? '',
            page: 1,
            pageSize: 100,
        }).subscribe({
            next: result => {
                this.groupMessages.set(key, result.items);
                this.groupLoading.delete(key);
            },
            error: error => {
                this.groupLoading.delete(key);
                this.error = error?.error?.message ?? 'Could not load grouped messages.';
            },
        });
    }

    confirmGroupAction(group: MessageHubDeliveryGroup, action: 'acknowledge' | 'cancel' | 'release'): void {
        const copy = {
            acknowledge: {
                title: 'Mark group as read',
                message: `Mark all ${group.count} matching messages from ${group.source_label} as read?`,
                label: 'Mark group read',
            },
            cancel: {
                title: 'Cancel group',
                message: `Cancel all ${group.count} matching messages from ${group.source_label}?`,
                label: 'Cancel group',
            },
            release: {
                title: 'Queue group for sending',
                message: `Queue all ${group.count} matching messages from ${group.source_label} for sending?`,
                label: 'Queue group',
            },
        }[action];
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {title: copy.title, message: copy.message, confirmLabel: copy.label},
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) this.runGroupAction(group, action);
        });
    }

    private runGroupAction(
        group: MessageHubDeliveryGroup,
        action: 'acknowledge' | 'cancel' | 'release',
    ): void {
        const key = this.groupKey(group);
        this.groupLoading.add(key);
        this.error = '';
        this.notice = '';
        this.hub.bulkGroupAction(group, action, this.deliveryFilters()).subscribe({
            next: result => {
                this.groupLoading.delete(key);
                this.groupMessages.delete(key);
                this.expandedGroups.delete(key);
                this.notice = result.truncated
                    ? `${result.updated} messages updated. More remain; repeat the action to continue.`
                    : `${result.updated} messages updated.`;
                this.pageIndex = 0;
                this.appliedCreatedBefore = new Date().toISOString();
                this.load();
            },
            error: error => {
                this.groupLoading.delete(key);
                this.error = error?.error?.message ?? 'Could not update the message group.';
            },
        });
    }

    isAllVisibleSelected(): boolean {
        if (this.allMatchingSelected) return true;
        const selectable = this.visibleDeliveries.slice(0, this.maxBulkSelection);
        return selectable.length > 0 && selectable.every(item => this.selected.has(item.id));
    }

    isSomeVisibleSelected(): boolean {
        if (this.allMatchingSelected) return false;
        const selectable = this.visibleDeliveries.slice(0, this.maxBulkSelection);
        const count = selectable.filter(item => this.selected.has(item.id)).length;
        return count > 0 && count < selectable.length;
    }

    toggleAllVisible(checked: boolean): void {
        if (this.allMatchingSelected) return;
        const selectable = this.visibleDeliveries.slice(0, this.maxBulkSelection);
        this.selected.clear();
        if (checked) selectable.forEach(item => this.selected.add(item.id));
        if (checked && this.visibleDeliveries.length > this.maxBulkSelection) {
            this.notice = `Selected the first ${this.maxBulkSelection} deliveries, the maximum for one bulk action.`;
        }
    }

    toggleSelected(delivery: MessageHubDelivery, checked: boolean): void {
        if (this.allMatchingSelected) return;
        if (checked && this.selected.size >= this.maxBulkSelection) {
            this.notice = `A bulk action can include at most ${this.maxBulkSelection} deliveries.`;
            return;
        }
        if (checked) this.selected.add(delivery.id);
        else this.selected.delete(delivery.id);
    }

    selectionHasOnly(...statuses: string[]): boolean {
        const selected = this.selectedDeliveries;
        return selected.length > 0 && selected.every(item => statuses.includes(item.status));
    }

    selectAllMatching(): void {
        if (!this.isAllVisibleSelected() || this.totalItems <= this.selected.size) return;
        this.allMatchingSelected = true;
        this.notice = '';
    }

    canAcknowledgeSelection(): boolean {
        return this.allMatchingSelected ? this.view === 'held' : this.selectionHasOnly('held');
    }

    canReleaseSelection(): boolean {
        return this.allMatchingSelected ? this.view === 'held' : this.selectionHasOnly('held');
    }

    canRetrySelection(): boolean {
        return !this.allMatchingSelected && this.selectionHasOnly('dead', 'retry_wait');
    }

    bulkActionLabel(action: MessageHubBulkAction): string {
        return {
            acknowledge: 'Marked as read',
            cancel: 'Cancelled',
            release: 'Queued for sending',
            retry: 'Retried',
        }[action];
    }

    confirmUndoOperation(operation: MessageHubBulkOperation): void {
        const remaining = operation.affected_count - operation.undone_count;
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {
                title: 'Undo bulk action',
                message: `Restore ${remaining} deliveries changed by this ${operation.action} action? Deliveries changed again since then will be skipped.`,
                confirmLabel: 'Undo action',
            },
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) this.undoOperation(operation.id);
        });
    }

    private undoOperation(operationId: number): void {
        this.operationBusy.add(operationId);
        this.error = '';
        this.notice = '';
        this.hub.undoBulkOperation(operationId).subscribe({
            next: result => {
                this.operationBusy.delete(operationId);
                this.notice = result.skipped
                    ? `${result.restored} deliveries restored; ${result.skipped} skipped because their state changed.`
                    : `${result.restored} deliveries restored.`;
                this.appliedCreatedBefore = new Date().toISOString();
                this.load();
            },
            error: error => {
                this.operationBusy.delete(operationId);
                this.error = error?.error?.message ?? 'Could not undo the bulk action.';
            },
        });
    }

    resumeOperation(operation: MessageHubBulkOperation): void {
        this.operationBusy.add(operation.id);
        this.error = '';
        this.notice = '';
        let updated = 0;
        const processNextBatch = (): void => {
            this.hub.resumeBulkOperation(operation.id).subscribe({
                next: result => {
                    updated += result.updated;
                    if (result.truncated && result.updated > 0) {
                        processNextBatch();
                        return;
                    }
                    this.operationBusy.delete(operation.id);
                    this.notice = `${updated} remaining deliveries updated.`;
                    this.appliedCreatedBefore = new Date().toISOString();
                    this.load();
                },
                error: error => {
                    this.operationBusy.delete(operation.id);
                    if (updated) {
                        this.notice = `${updated} deliveries were updated before resume stopped. The operation can be resumed again.`;
                        this.load();
                    } else {
                        this.error = error?.error?.message ?? 'Could not resume the bulk action.';
                    }
                },
            });
        };
        processNextBatch();
    }

    queueBuckets(gateway: MessageHubGatewayStats): Array<{status: string} & MessageHubQueueBucket> {
        return Object.entries(gateway.deliveries)
            .filter(([, value]) => value.count > 0)
            .map(([status, value]) => ({status, ...value}));
    }

    messageText(delivery: MessageHubDelivery): string {
        return String(delivery.payload['text'] ?? delivery.payload['message'] ?? '<message>');
    }

    toggleExpanded(delivery: MessageHubDelivery): void {
        if (this.expanded.has(delivery.id)) this.expanded.delete(delivery.id);
        else this.expanded.add(delivery.id);
    }

    attachmentSize(): string {
        const bytes = this.stats.attachments.size_bytes;
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    retry(delivery: MessageHubDelivery): void {
        this.run(delivery, () => this.hub.retry(delivery.id));
    }

    confirmRetryAnyway(delivery: MessageHubDelivery): void {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {
                title: 'Retry uncertain delivery',
                message: `Delivery ${delivery.id} may already have been sent. Sending it again can create a duplicate. Continue?`,
                confirmLabel: 'Retry anyway',
            },
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) this.run(delivery, () => this.hub.retryAnyway(delivery.id));
        });
    }

    release(delivery: MessageHubDelivery): void {
        this.run(delivery, () => this.hub.release(delivery.id));
    }

    confirmRelease(delivery: MessageHubDelivery): void {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {
                title: 'Queue message for sending',
                message: `Release delivery ${delivery.id}? It will be queued for sending through the gateway.`,
                confirmLabel: 'Queue for sending',
            },
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) this.release(delivery);
        });
    }

    confirmCancel(delivery: MessageHubDelivery): void {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {
                title: 'Cancel delivery',
                message: `Cancel delivery ${delivery.id} to ${delivery.recipient_key}?`,
                confirmLabel: 'Cancel delivery',
            },
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) this.run(delivery, () => this.hub.cancel(delivery.id));
        });
    }

    openDetails(delivery: MessageHubDelivery): void {
        const ref = this.dialog.open<
            DeliveryDetailsDialogComponent,
            number,
            DeliveryDetailsDialogResult
        >(DeliveryDetailsDialogComponent, {
            data: delivery.id,
            width: '900px',
            maxWidth: '95vw',
        });
        ref.afterClosed().subscribe(result => {
            if (!result) return;
            if (result.action === 'acknowledge') {
                this.acknowledge(result.delivery);
            } else if (result.action === 'release') {
                this.confirmRelease(result.delivery);
            } else if (result.action === 'cancel') {
                this.confirmCancel(result.delivery);
            } else if (result.action === 'retry') {
                this.retry(result.delivery);
            } else if (result.action === 'retry-anyway') {
                this.confirmRetryAnyway(result.delivery);
            }
        });
    }

    acknowledge(delivery: MessageHubDelivery): void {
        this.runBulkAction('acknowledge', [delivery.id]);
    }

    confirmBulkAction(action: MessageHubBulkAction): void {
        const deliveries = this.selectedDeliveries;
        if (!this.allMatchingSelected && !deliveries.length) return;
        const count = this.selectionCount;
        const messages = count === 1 ? 'message' : 'messages';
        const deliveryLabel = count === 1 ? 'delivery' : 'deliveries';
        const selectionLabel = this.allMatchingSelected ? 'matching filtered' : 'selected';
        const descriptions: Record<MessageHubBulkAction, {title: string; message: string; label: string}> = {
            acknowledge: {
                title: 'Mark messages as read',
                message: `Mark ${count} held ${messages} as read? ${count === 1 ? 'It' : 'They'} will leave the held inbox and will not be sent.`,
                label: 'Mark as read',
            },
            cancel: {
                title: 'Cancel deliveries',
                message: `Cancel ${count} ${selectionLabel} ${deliveryLabel}? ${count === 1 ? 'It' : 'They'} will not be sent.`,
                label: 'Cancel deliveries',
            },
            release: {
                title: 'Queue messages for sending',
                message: `Release ${count} held ${messages}? ${count === 1 ? 'It' : 'They'} will be queued for sending through the gateway.`,
                label: 'Queue for sending',
            },
            retry: {
                title: 'Retry deliveries',
                message: `Retry ${count} ${selectionLabel} ${deliveryLabel} now?`,
                label: 'Retry deliveries',
            },
        };
        const copy = descriptions[action];
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {title: copy.title, message: copy.message, confirmLabel: copy.label},
            width: '500px',
            maxWidth: '90vw',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (!confirmed) return;
            if (this.allMatchingSelected) this.runFilteredBulkAction(action);
            else this.runBulkAction(action, deliveries.map(item => item.id));
        });
    }

    private runFilteredBulkAction(action: MessageHubBulkAction): void {
        this.bulkBusy = true;
        this.error = '';
        this.notice = '';
        const filters = this.deliveryFilters();
        let updated = 0;
        let operationId: number | undefined;
        this.bulkProgressUpdated = 0;
        this.bulkProgressTotal = this.selectionCount;

        const processNextBatch = (): void => {
            this.hub.bulkFilteredAction(filters, action, operationId).subscribe({
                next: result => {
                    updated += result.updated;
                    operationId = result.operation?.id ?? operationId;
                    this.bulkProgressUpdated = updated;
                    if (result.truncated && result.updated > 0) {
                        processNextBatch();
                        return;
                    }
                    this.bulkBusy = false;
                    this.bulkProgressUpdated = 0;
                    this.bulkProgressTotal = 0;
                    this.clearSelection();
                    const label = updated === 1 ? 'delivery' : 'deliveries';
                    this.notice = `${updated} matching ${label} updated.`;
                    this.pageIndex = 0;
                    this.appliedCreatedBefore = new Date().toISOString();
                    this.load();
                },
                error: error => {
                    this.bulkBusy = false;
                    this.bulkProgressUpdated = 0;
                    this.bulkProgressTotal = 0;
                    this.clearSelection();
                    if (updated > 0) {
                        this.notice = `${updated} matching deliveries were updated before the operation stopped. Use Resume in Recent bulk actions to continue the same snapshot.`;
                        this.pageIndex = 0;
                        this.load();
                    } else {
                        this.error = error?.error?.message ?? 'Could not update the matching deliveries.';
                    }
                },
            });
        };

        processNextBatch();
    }

    private runBulkAction(action: MessageHubBulkAction, deliveryIds: number[]): void {
        this.bulkBusy = true;
        this.error = '';
        this.notice = '';
        this.hub.bulkAction(deliveryIds, action).subscribe({
            next: result => {
                this.bulkBusy = false;
                this.clearSelection();
                if (result.skipped.length) {
                    this.notice = `${result.updated} updated; ${result.skipped.length} skipped because their state changed.`;
                } else {
                    const label = result.updated === 1 ? 'delivery' : 'deliveries';
                    this.notice = `${result.updated} ${label} updated.`;
                }
                this.pageIndex = 0;
                this.appliedCreatedBefore = new Date().toISOString();
                this.load();
            },
            error: error => {
                this.bulkBusy = false;
                this.error = error?.error?.message ?? 'Could not update the selected deliveries.';
            },
        });
    }

    private run(delivery: MessageHubDelivery, action: () => ReturnType<MessageHubService['retry']>): void {
        this.busy.add(delivery.id);
        this.error = '';
        action().subscribe({
            next: () => {
                this.busy.delete(delivery.id);
                this.pageIndex = 0;
                this.appliedCreatedBefore = new Date().toISOString();
                this.load();
            },
            error: error => {
                this.busy.delete(delivery.id);
                this.error = error?.error?.message ?? `Could not update delivery ${delivery.id}.`;
            },
        });
    }
}
