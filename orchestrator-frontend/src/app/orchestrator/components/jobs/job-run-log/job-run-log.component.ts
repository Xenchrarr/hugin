import {Component, Inject, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked, inject} from '@angular/core';
import {
    MAT_DIALOG_DATA,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle
} from "@angular/material/dialog";
import {MatButton} from "@angular/material/button";
import {JobLog} from "../../../models/job-log";
import {JobLogsService} from "../../../services/job-logs.service";
import {
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell,
    MatHeaderCellDef,
    MatHeaderRow, MatHeaderRowDef, MatRow, MatRowDef,
    MatTable
} from "@angular/material/table";
import {JobRun} from "../../../models/job-run";
import {TimeService} from "../../../services/time.service";
import {NgClass} from "@angular/common";
import {FormsModule} from "@angular/forms";
import {MatCheckbox} from "@angular/material/checkbox";
import {Subscription, interval} from "rxjs";
import {JobRunService} from "../../../services/job-run.service";
import {MatSnackBar} from "@angular/material/snack-bar";
import {NotificationComponent} from "../../notification/notification.component";
import {NgIf} from "@angular/common";

@Component({
    selector: 'app-job-run-log',
    standalone: true,
    imports: [
        MatDialogActions,
        MatDialogClose,
        MatDialogContent,
        MatDialogTitle,
        MatButton,
        MatTable,
        MatColumnDef,
        MatHeaderCell,
        MatCell,
        MatHeaderCellDef,
        MatCellDef,
        MatHeaderRow,
        MatRow,
        MatHeaderRowDef,
        MatRowDef,
        NgClass,
        NgIf,
        FormsModule,
        MatCheckbox,
    ],
    templateUrl: './job-run-log.component.html',
    styleUrl: './job-run-log.component.css',

})
export class JobRunLogComponent implements OnInit, OnDestroy, AfterViewChecked {

    jobLogs: JobLog[] = [];
    displayedColumns: string[] = ['created_at', 'log_level', 'message', 'stack_trace'];
    availableColumns: string[] = ['id', 'job_run']
    autoScroll = true;
    reason: { selected: string | null; freeText: string | null } | null = null;
    private pollSubscription?: Subscription;
    private shouldScroll = false;
    private _snackBar = inject(MatSnackBar);

    @ViewChild('scrollContainer') private scrollContainer!: ElementRef<HTMLElement>;

    constructor(@Inject(MAT_DIALOG_DATA) public data: JobRun,
                private jobLogService: JobLogsService,
                private jobRunService: JobRunService,
                private timeService: TimeService) {

    }

    cancelJob(): void {
        this.jobRunService.cancelJobRun(String(this.data.id)).subscribe({
            next: () => {
                this._snackBar.openFromComponent(NotificationComponent, {
                    duration: 5000,
                    horizontalPosition: 'center',
                    verticalPosition: 'top',
                    data: { message: 'Cancellation requested', type: 'default' },
                });
            },
            error: (err) => {
                const msg = err.error?.message || 'Failed to cancel job';
                this._snackBar.openFromComponent(NotificationComponent, {
                    duration: 5000,
                    horizontalPosition: 'center',
                    verticalPosition: 'top',
                    data: { message: msg, type: 'error' },
                });
            }
        });
    }

    ngOnInit(): void {
        if (this.data.id) {
            this.reload_logs();
            this.startPolling();
            this.loadReason();
        }
    }

    ngOnDestroy(): void {
        this.stopPolling();
    }

    ngAfterViewChecked(): void {
        if (this.shouldScroll && this.autoScroll) {
            this.scrollToBottom();
            this.shouldScroll = false;
        }
    }

    private scrollToBottom(): void {
        const el = this.scrollContainer?.nativeElement;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }

    private startPolling(): void {
        this.pollSubscription = interval(500).subscribe(() => {
            this.reload_logs();
            this.checkJobStatus();
        });
    }

    private stopPolling(): void {
        this.pollSubscription?.unsubscribe();
    }

    private checkJobStatus(): void {
        this.jobRunService.getJobRun(this.data.id).subscribe(jobRun => {
            if (jobRun && jobRun.status !== 'Started') {
                this.data.status = jobRun.status;
                this.stopPolling();
                this.reload_logs();
            }
        });
    }

    private loadReason(): void {
        this.jobRunService.getJobRun(this.data.id).subscribe(jobRun => {
            if (jobRun?.metadata?.['reason']) {
                this.reason = jobRun.metadata['reason'];
            }
        });
    }

    reload_logs() {
        this.jobLogService.getLogsForJob(this.data.id).subscribe(log => {
            if (log.length !== this.jobLogs.length) {
                this.shouldScroll = true;
            }
            this.jobLogs = log;
        });
    }

    getFormattedDate(date: string): string {
        return this.timeService.formatDate(date);
    }

    containsLink(text: string | undefined): boolean {
        if (!text) {
            return false;
        }

        return text.startsWith('/logs/') || text.includes('https://nssarms.blob.core.windows.net/');
    }

    getFormattedJson(jsonData: string) {
        if (jsonData === undefined || jsonData === null) {
            return ""
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

}
