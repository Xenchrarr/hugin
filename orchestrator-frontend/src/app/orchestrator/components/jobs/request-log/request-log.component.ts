import {Component, inject, Inject, OnInit} from '@angular/core';
import {MatButton, MatIconButton} from "@angular/material/button";
import {
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell, MatHeaderCellDef,
    MatHeaderRow,
    MatHeaderRowDef,
    MatRow, MatRowDef, MatTable
} from "@angular/material/table";
import {
    MAT_DIALOG_DATA, MatDialog,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle
} from "@angular/material/dialog";
import {JobLog} from "../../../models/job-log";
import {JobRun} from "../../../models/job-run";
import {JobLogsService} from "../../../services/job-logs.service";
import {animate, state, style, transition, trigger} from "@angular/animations";
import {MatIcon} from "@angular/material/icon";
import {NgClass} from "@angular/common";
import {TimeService} from "../../../services/time.service";
import {MatPaginator, PageEvent} from "@angular/material/paginator";

@Component({
    selector: 'app-request-log',
    standalone: true,
    imports: [
        MatButton,
        MatCell,
        MatCellDef,
        MatColumnDef,
        MatDialogActions,
        MatDialogClose,
        MatDialogContent,
        MatDialogTitle,
        MatHeaderCell,
        MatHeaderRow,
        MatHeaderRowDef,
        MatRow,
        MatRowDef,
        MatTable,
        MatHeaderCellDef,
        MatIcon,
        MatIconButton,
        NgClass,
        MatPaginator
    ],
    templateUrl: './request-log.component.html',
    styleUrl: './request-log.component.css',
    animations: [
        trigger('detailExpand', [
            state('collapsed,void', style({height: '0px', minHeight: '0'})),
            state('expanded', style({height: '*'})),
            transition('expanded <=> collapsed', animate('225ms cubic-bezier(0.4, 0.0, 0.2, 1)')),
        ]),
    ]
})
export class RequestLogComponent implements OnInit  {
    jobLogs: JobLog[] = [];
    displayedColumns: string[] = ['created', 'api_name', 'description', 'area', 'request_type', 'function_name', 'response_code'];
    availableColumns: string[] = ['id', 'job_run',  'request_data', 'response' ]
    columnsToDisplayWithExpand = [...this.displayedColumns, 'expand'];

    pageSize: number = 10;
    currentPage: number = 0;
    totalItems: number = 0;
    pageSizeOptions = [10, 25, 100, 500];

    expandedElement: JobLog | null | undefined;
    readonly dialog = inject(MatDialog);

    constructor(@Inject(MAT_DIALOG_DATA) public data: JobRun,
                private jobLogService: JobLogsService,
                private timeService: TimeService) {

    }

    ngOnInit(): void {
        if (this.data.id) {
            this.reload_logs(this.currentPage, this.pageSize);
            this.getTotalItems();
        }
    }

    getTotalItems(){
        this.jobLogService.getTotalNumRequestLogsForJob(this.data.id).subscribe(total => {
            this.totalItems = total;
        });
    }

    reload_logs(page: number, pageSize: number) {
        this.jobLogService.getRequestLogsForJob(this.data.id, page + 1, pageSize).subscribe(log => {
            console.log(log);
            this.jobLogs = log;
        });

    }

    pageChanged(event: PageEvent) {
        this.currentPage = event.pageIndex;
        this.pageSize = event.pageSize;
        this.reload_logs(this.currentPage, this.pageSize);
    }

    reload() {
        this.reload_logs(this.currentPage, this.pageSize);
        this.getTotalItems();
    }

    setPageSizeOptions(setPageSizeOptionsInput: string) {
        if (setPageSizeOptionsInput) {
            this.pageSizeOptions = setPageSizeOptionsInput.split(',').map(str => +str);
        }
    }

    containsLink(text: string): boolean {
        if (text === undefined || text === null) {
            return false;
        }
        return text.startsWith('/logs/') || text.includes('https://nssarms.blob.core.windows.net/');
    }

    getFormattedJson(jsonData: string) {
        if (jsonData === undefined || jsonData === null) {
            jsonData = '{}';
        }
        let data = "";
        try {
            data =  JSON.stringify(JSON.parse(this.replaceSingleQuotes(jsonData)), null, 2)

        }
        catch (e) {
            data = jsonData;
        }
        return data;
    }

    replaceSingleQuotes(str: string): string {
        return str.replace(/'/g, '"');
    }

    getClassFromResponseCode(responseCode: number): string {
        if (responseCode >= 200 && responseCode < 300) {
            return 'success';
        } else if (responseCode >= 300 && responseCode < 400) {
            return 'redirect';
        } else if (responseCode >= 400 && responseCode < 500) {
            return 'client-error';
        } else if (responseCode >= 500 && responseCode < 600) {
            return 'server-error';
        } else {
            return 'unknown';
        }
    }

    getFormattedDate(date: string): string {
        return this.timeService.formatDate(date);
    }

}
