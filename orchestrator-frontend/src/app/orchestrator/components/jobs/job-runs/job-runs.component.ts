import {Component, inject, OnInit} from '@angular/core';
import {JobRun} from "../../../models/job-run";
import {JobRunService} from "../../../services/job-run.service";
import {NgClass, NgForOf, NgIf} from "@angular/common";
import {MatPaginator, PageEvent} from "@angular/material/paginator";
import {
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell,
    MatHeaderCellDef,
    MatHeaderRow, MatHeaderRowDef, MatRow, MatRowDef,
    MatTable
} from "@angular/material/table";
import {MatIcon} from "@angular/material/icon";
import {animate, state, style, transition, trigger} from "@angular/animations";
import {MatButton, MatIconButton} from "@angular/material/button";
import {MatDialog} from "@angular/material/dialog";
import {ConfirmDialogComponent} from '../../confirm-dialog/confirm-dialog.component';
import {JobRunLogComponent} from "../job-run-log/job-run-log.component";
import {RequestLogComponent} from "../request-log/request-log.component";
import {TimeService} from "../../../services/time.service";
import {JobService} from "../../../services/job.service";
import {MatCheckbox} from "@angular/material/checkbox";
import {FormsModule} from "@angular/forms";
import {MatSnackBar} from "@angular/material/snack-bar";
import {NotificationComponent} from "../../notification/notification.component";

@Component({
    selector: 'app-job-runs',
    standalone: true,
    imports: [
        NgForOf,
        MatPaginator,
        MatTable,
        MatColumnDef,
        MatHeaderCell,
        MatCell,
        MatHeaderCellDef,
        MatCellDef,
        MatHeaderRow,
        MatHeaderRowDef,
        MatRowDef,
        MatRow,
        MatIcon,
        MatIconButton,
        MatButton,
        NgClass,
        NgIf,
        MatCheckbox,
        FormsModule
    ],
    templateUrl: './job-runs.component.html',
    styleUrl: './job-runs.component.css',
    animations: [
        trigger('detailExpand', [
            state('collapsed,void', style({height: '0px', minHeight: '0'})),
            state('expanded', style({height: '*'})),
            transition('expanded <=> collapsed', animate('225ms cubic-bezier(0.4, 0.0, 0.2, 1)')),
        ]),
    ],
})
export class JobRunsComponent implements OnInit{
    jobRuns: JobRun[] = [];
    groupingValues: any[] = [];

    statusValues: any[] = [];

    pageSize: number = 10;
    currentPage: number = 0;
    totalItems: number = 0;

    displayedColumns: string[] = ['name', 'executed_by', 'start_time', 'status', 'result', 'reason'];
    columnsToDisplayWithExpand = [...this.displayedColumns, 'expand'];
    expandedElement: JobRun | null | undefined;

    readonly dialog = inject(MatDialog);
    private _snackBar = inject(MatSnackBar);

    constructor(private jobRunService: JobRunService,
                private timeService: TimeService,
                private jobService: JobService) {
    }

    ngOnInit(): void {
        // this.reloadJobRuns(this.currentPage, this.pageSize);
        // this.getTotalItems();
        this.getGroupingValues();
        this.getStatusValues();
    }

    reloadJobRuns(page: number, pageSize: number){
        const selectedGrouping: string[] = this.groupingValues
            .filter(group => group.checked)
            .map(group => group.name);

        const selectedStatus: string[] = this.statusValues
            .filter(group => group.checked)
            .map(group => group.name);

        // console.log('Selected items:', selectedItems);
        this.jobRunService.getJobRuns(page + 1, pageSize, selectedGrouping, selectedStatus).subscribe(jobRuns => {
            this.jobRuns = jobRuns;
        });
    }

    reload(){
        this.reloadJobRuns(this.currentPage, this.pageSize);
        this.getTotalItems();
    }

    pageChanged(event: PageEvent) {
        this.currentPage = event.pageIndex;
        this.reloadJobRuns(this.currentPage, this.pageSize);
    }

    getTotalItems(){
        const selectedItems: string[] = this.groupingValues
            .filter(group => group.checked)
            .map(group => group.name);

        const selectedStatus: string[] = this.statusValues
            .filter(group => group.checked)
            .map(group => group.name);

        this.jobRunService.getTotalJobRuns(selectedItems, selectedStatus).subscribe(total => {
            this.totalItems = total;
        });
    }

    openLogs(jobRun: JobRun){
        console.log(jobRun);
        const dialogRef = this.dialog.open(JobRunLogComponent, {data: jobRun, width: '1000px', height: '1000px', maxWidth: '2000px', maxHeight: '2000px'});
        dialogRef.afterClosed().subscribe(result => {
            console.log(`Dialog result: ${result}`);
        });
    }

    openRequests(jobRun: JobRun) {
        console.log(jobRun);
        const dialogRef = this.dialog.open(RequestLogComponent, {
            data: jobRun,
            width: '1400px',
            height: '1000px',
            maxWidth: '2000px',
            maxHeight: '2000px'
        });
        dialogRef.afterClosed().subscribe(result => {
            console.log(`Dialog result: ${result}`);
        });
    }

    print(text: string){
        console.log(text);
    }

    getFormattedDate(date: string): string {
        return this.timeService.formatDate(date);
    }

    getShortName(name: string){

        if (!name.includes('/') ) {
            return name;
        }
        let shortName = name.split('/')



        return shortName[shortName.length-1]
    }

    getGroupingValues(){
        this.jobService.getGroupingValues().subscribe((groupingValues: string[]) => {
            // this.groupingValues = groupingValues;
            for (let i = 0; i < groupingValues.length; i++) {
                this.groupingValues.push({name: groupingValues[i], checked: false})
            }
        })
    }


    getStatusValues(){
        this.jobService.getStatusValues().subscribe((statusValues: string[]) => {
            // this.groupingValues = groupingValues;
            for (let i = 0; i < statusValues.length; i++) {
                let checked = true;
                if (statusValues[i] == 'Nothing'){
                    checked = false;
                }
                this.statusValues.push({name: statusValues[i], checked: checked})
            }

            this.reload();
        })
    }

    updateGroupingStatus(taskIndex: number, checked: boolean) {
        this.groupingValues[taskIndex].checked = checked;
        this.reloadJobRuns(this.currentPage, this.pageSize);
        this.getTotalItems();
    }

    updateStatus(taskIndex: number, checked: boolean) {
        this.statusValues[taskIndex].checked = checked;
        this.reloadJobRuns(this.currentPage, this.pageSize);
        this.getTotalItems();
    }

    getStatusText(status: string) {
        if (status == 'Nothing') {
            return 'Nothing to do';
        }
        if (status == 'Partial') {
            return 'Partial success';
        }
        return status;
    }

    cancelJobRun(jobRun: JobRun): void {
        this.jobRunService.cancelJobRun(String(jobRun.id)).subscribe({
            next: () => {
                this._snackBar.openFromComponent(NotificationComponent, {
                    duration: 5000,
                    horizontalPosition: 'center',
                    verticalPosition: 'top',
                    data: { message: 'Cancellation requested', type: 'default' },
                });
                this.reload();
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


    confirmDeleteJobRun(jobRun: JobRun): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            data: { title: 'Delete Run?', message: `Are you sure you want to delete "${jobRun.name || jobRun.id}"?`, confirmLabel: 'Delete' },
            width: '400px',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.deleteJobRun(jobRun);
            }
        });
    }

    deleteJobRun(jobRun: JobRun): void {
        this.jobRunService.deleteJobRun(String(jobRun.id)).subscribe({
            next: () => {
                this._snackBar.openFromComponent(NotificationComponent, {
                    duration: 5000,
                    horizontalPosition: 'center',
                    verticalPosition: 'top',
                    data: { message: 'Job run deleted', type: 'default' },
                });
                this.reload();
            },
            error: (err) => {
                const msg = err.error?.message || 'Failed to delete job run';
                this._snackBar.openFromComponent(NotificationComponent, {
                    duration: 5000,
                    horizontalPosition: 'center',
                    verticalPosition: 'top',
                    data: { message: msg, type: 'error' },
                });
            }
        });
    }


}
