import {Component, inject, OnInit} from '@angular/core';
import {Job} from "../../../models/job";
import {JobType} from "../../../models/job-type";
import {JobService} from "../../../services/job.service";
import {TimeService} from "../../../services/time.service";
import {animate, state, style, transition, trigger} from "@angular/animations";
import {JobRun} from "../../../models/job-run";
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
import {MatIcon} from "@angular/material/icon";
import {MatPaginator} from "@angular/material/paginator";
import {KeyValuePipe, NgClass, NgForOf, NgIf} from "@angular/common";
import {MatCheckbox} from "@angular/material/checkbox";
import {MatFormField} from "@angular/material/form-field";
import {MatInput} from "@angular/material/input";
import {ReactiveFormsModule} from "@angular/forms";
import {JobRunLogComponent} from "../job-run-log/job-run-log.component";
import {JobCardNewComponent} from "../job-card-new/job-card-new.component";
import {MatDialog} from "@angular/material/dialog";
import {ConfirmDialogComponent} from '../../confirm-dialog/confirm-dialog.component';

@Component({
    selector: 'app-job-settings-new',
    standalone: true,
    imports: [
        MatButton,
        MatCell,
        MatCellDef,
        MatColumnDef,
        MatHeaderCell,
        MatHeaderRow,
        MatHeaderRowDef,
        MatIcon,
        MatIconButton,
        MatPaginator,
        MatRow,
        MatRowDef,
        MatTable,
        MatHeaderCellDef,
        NgClass,
        MatCheckbox,
        NgIf,
        MatFormField,
        MatInput,
        ReactiveFormsModule,
        KeyValuePipe,
        NgForOf
    ],
    templateUrl: './job-settings-new.component.html',
    styleUrl: './job-settings-new.component.css',
    animations: [
        trigger('detailExpand', [
            state('collapsed,void', style({height: '0px', minHeight: '0'})),
            state('expanded', style({height: '*'})),
            transition('expanded <=> collapsed', animate('225ms cubic-bezier(0.4, 0.0, 0.2, 1)')),
        ]),

    ],
})
export class JobSettingsNewComponent implements OnInit {
    jobs: Job[] = [];
    groupedJobs: { [key: string]: Job[] } = {};
    job_types: JobType[] = [];
    readonly dialog = inject(MatDialog);


    displayedColumns: string[] = ['id', 'job_type', 'name', 'trigger','running_at','enabled',];
    columnsToDisplayWithExpand = [...this.displayedColumns, 'expand'];
    expandedElement: Job | null | undefined;




    constructor(private jobService: JobService,
                private timeService: TimeService) {

    }

    ngOnInit() {
        this.reloadJobs()

        // this.jobService.getJobTypes().subscribe(job_types => {
        //     this.job_types = job_types;
        // });
    }

    reloadJobs(){
        this.jobService.getJobs().subscribe(jobs => {
            this.jobs = jobs;
            this.groupJobsByGroupingValue();
            console.log(this.jobs)

        });
    }

    groupJobsByGroupingValue() {
        this.groupedJobs = this.jobs.reduce((groups, job) => {
            const key = job.grouping_value || 'Ungrouped';
            if (!groups[key]) {
                groups[key] = [];
            }
            groups[key].push(job);
            return groups;
        }, {} as { [key: string]: Job[] });
    }

    getFormattedDate(date: string): string {
        return this.timeService.formatDate(date);
    }

    editJob(job: Job){
        console.log(job);

        const dialogRef = this.dialog.open(JobCardNewComponent, {data: job, width: '1000px', height: '1000px', maxWidth: '2000px', maxHeight: '2000px'});
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.reloadJobs();
            }
        });
    }

    addJob() {
        const dialogRef = this.dialog.open(JobCardNewComponent, {data: undefined, width: '1000px', height: '1000px', maxWidth: '2000px', maxHeight: '2000px'});
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.reloadJobs();
            }
        })
    }

    startJobNow(job: Job){
        this.jobService.startJob(job).subscribe(response => {
            if (response?.job_run_id) {
                const jobRun = new JobRun({
                    id: response.job_run_id as any,
                    name: job.name,
                    status: 'Started',
                    job_type: job.job_type,
                    job_id: job.id,
                });
                this.dialog.open(JobRunLogComponent, {
                    data: jobRun,
                    width: '1200px',
                    maxWidth: '95vw',
                    maxHeight: '90vh',
                });
            }
        });
    }


        confirmDeleteJob(job: Job): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            data: { title: 'Delete Job?', message: `Are you sure you want to delete "${job.name || job.id}"?`, confirmLabel: 'Delete' },
            width: '500px',
            maxWidth: '90vw',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.deleteJob(job);
            }
        });
    }

    deleteJob(job: Job): void {
        this.jobService.deleteJob(job).subscribe({
            next: () => {
                this.reloadJobs();
            },
            error: (err) => {
                // Optionally show a notification here
                this.reloadJobs();
            }
        });
    }

}
