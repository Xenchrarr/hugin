import {Component, EventEmitter, Inject, Input, Output} from '@angular/core';
import {MatButton} from "@angular/material/button";
import {
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell,
    MatHeaderRow,
    MatHeaderRowDef,
    MatRow, MatRowDef, MatTable
} from "@angular/material/table";
import {
    MAT_DIALOG_DATA,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent, MatDialogRef,
    MatDialogTitle
} from "@angular/material/dialog";
import {Job} from "../../../models/job";
import {JobType} from "../../../models/job-type";
import {JobRun} from "../../../models/job-run";
import {JobService} from "../../../services/job.service";
import {MatCard, MatCardActions, MatCardContent, MatCardHeader, MatCardTitle} from "@angular/material/card";
import {MatCheckbox} from "@angular/material/checkbox";
import {MatFormField, MatLabel} from "@angular/material/form-field";
import {MatIcon} from "@angular/material/icon";
import {MatInput} from "@angular/material/input";
import {FormsModule, ReactiveFormsModule} from "@angular/forms";
import {TimeService} from "../../../services/time.service";
import {MatOption, MatSelect, MatSelectModule} from "@angular/material/select";
import {NgForOf} from "@angular/common";
import {GitRepo} from "../../../models/git-repo";
import {GitRepoService} from "../../../services/git-repo.service";

@Component({
    selector: 'app-job-card-new',
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
        MatCard,
        MatSelectModule,
        MatCardActions,
        MatCardContent,
        MatCardHeader,
        MatCardTitle,
        MatCheckbox,
        MatFormField,
        MatIcon,
        MatInput,
        MatLabel,
        ReactiveFormsModule,
        FormsModule,
        MatOption,
        NgForOf
    ],
    templateUrl: './job-card-new.component.html',
    styleUrl: './job-card-new.component.css'
})
export class JobCardNewComponent {
    @Input() job: Job;
    job_types: JobType[] = [];
    repos: GitRepo[] = [];

    @Output() jobSaved = new EventEmitter<Job>();
    isNew = false
    editMode: boolean = true;



    constructor(@Inject(MAT_DIALOG_DATA) public data: Job,
                private jobService: JobService,
                private timeService: TimeService,
                private repoService: GitRepoService,
                private dialogRef: MatDialogRef<JobCardNewComponent> // Inject MatDialogRef

    ) {
        this.getJobTypes();

        if (!data) {
            this.job = new Job();
            this.isNew = true;
            return;
        }
        this.job = data;
        if (this.job.job_type === 'git_sync') {
            this.loadRepos();
        }
    }


    saveJob() {
        this.jobService.saveJob(this.job).subscribe(job => {
            this.job = job;
            this.dialogRef.close(job); // Close the dialog
            this.jobSaved.emit(this.job);
        })


    }

    isWeeklyJob(): boolean {
        return this.job.trigger == "weekly";
    }

    getFormattedDate(date: string | undefined): string {
        return  this.timeService.formatDate(date);
    }

    deleteJob() {
        this.jobService.deleteJob(this.job).subscribe(() => {
            this.jobSaved.emit(this.job);
            this.dialogRef.close(); // Close the dialog
        })
    }

    getJobTypes() {
        this.jobService.getJobTypes().subscribe(job_types => {
            console.log(job_types);
            this.job_types = job_types;
        })
    }

    onJobTypeChange(selectedJobType: string) {
        const selectedType = this.job_types.find(type => type.job_type === selectedJobType);
        if (selectedType) {
            this.job.description = selectedType.description;
        }
        if (selectedJobType === 'git_sync') {
            this.loadRepos();
        }
    }

    isGitSyncJob(): boolean {
        return this.job.job_type === 'git_sync';
    }

    loadRepos() {
        this.repoService.getRepos().subscribe(repos => {
            this.repos = repos;
        });
    }
}
