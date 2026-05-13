import {Component, inject, OnInit} from '@angular/core';
import {NgIf, NgFor} from '@angular/common';
import {MatButton, MatIconButton} from '@angular/material/button';
import {MatButtonToggle, MatButtonToggleGroup} from '@angular/material/button-toggle';
import {MatIcon} from '@angular/material/icon';
import {MatDialog} from '@angular/material/dialog';
import {
    MatCell, MatCellDef, MatColumnDef,
    MatHeaderCell, MatHeaderCellDef,
    MatHeaderRow, MatHeaderRowDef,
    MatRow, MatRowDef, MatTable
} from '@angular/material/table';
import {MatSlideToggle} from '@angular/material/slide-toggle';
import {FormsModule} from '@angular/forms';
import {IcalService} from '../../services/ical.service';
import {CalendarEvent, IcalSource} from '../../models/ical-source';
import {SourceDialogComponent} from './source-dialog/source-dialog.component';
import {ConfirmDialogComponent} from '../confirm-dialog/confirm-dialog.component';
import {AgendaViewComponent} from './agenda-view/agenda-view.component';
import {WeekViewComponent} from './week-view/week-view.component';

@Component({
    selector: 'app-calendar',
    standalone: true,
    imports: [
        NgIf,
        NgFor,
        FormsModule,
        MatButton,
        MatIconButton,
        MatButtonToggle,
        MatButtonToggleGroup,
        MatIcon,
        MatTable,
        MatColumnDef,
        MatHeaderCell,
        MatHeaderCellDef,
        MatCell,
        MatCellDef,
        MatHeaderRow,
        MatHeaderRowDef,
        MatRow,
        MatRowDef,
        MatSlideToggle,
        AgendaViewComponent,
        WeekViewComponent,
    ],
    templateUrl: './calendar.component.html',
    styleUrl: './calendar.component.scss',
})
export class CalendarComponent implements OnInit {
    sources: IcalSource[] = [];
    events: CalendarEvent[] = [];
    view: 'agenda' | 'week' = 'agenda';
    loading = false;

    displayedColumns = ['name', 'url', 'enabled', 'actions'];

    readonly dialog = inject(MatDialog);

    constructor(private icalService: IcalService) {}

    ngOnInit() {
        this.loadSources();
        this.loadEvents();
    }

    loadSources() {
        this.icalService.getSources().subscribe(sources => (this.sources = sources));
    }

    loadEvents() {
        this.loading = true;
        this.icalService.getAgenda(14).subscribe({
            next: events => {
                this.events = events;
                this.loading = false;
            },
            error: () => {
                this.loading = false;
            },
        });
    }

    addSource() {
        const ref = this.dialog.open(SourceDialogComponent, {data: undefined, width: '500px'});
        ref.afterClosed().subscribe(result => {
            if (result) {
                this.loadSources();
                this.loadEvents();
            }
        });
    }

    editSource(source: IcalSource) {
        const ref = this.dialog.open(SourceDialogComponent, {data: source, width: '500px'});
        ref.afterClosed().subscribe(result => {
            if (result) {
                this.loadSources();
                this.loadEvents();
            }
        });
    }

    deleteSource(source: IcalSource) {
        const ref = this.dialog.open(ConfirmDialogComponent, {
            data: {message: `Delete "${source.name}"?`},
            width: '360px',
        });
        ref.afterClosed().subscribe(confirmed => {
            if (confirmed) {
                this.icalService.deleteSource(source.id).subscribe(() => {
                    this.loadSources();
                    this.loadEvents();
                });
            }
        });
    }

    toggleEnabled(source: IcalSource) {
        this.icalService.updateSource(source.id, {
            name: source.name,
            url: source.url,
            enabled: source.enabled,
        }).subscribe(() => this.loadEvents());
    }
}
