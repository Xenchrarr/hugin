import {Component, EventEmitter, Inject, Input, Output, ViewChild} from '@angular/core';
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
import {WorkflowInputEditorComponent} from '../../workflows/shared/workflow-input-editor.component';
import {exampleInput} from '../../workflows/shared/workflow-format';

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
        NgForOf,
        WorkflowInputEditorComponent
    ],
    templateUrl: './job-card-new.component.html',
    styleUrl: './job-card-new.component.css'
})
export class JobCardNewComponent {
    @ViewChild(WorkflowInputEditorComponent) inputEditor?: WorkflowInputEditorComponent;
    @Input() job: Job;
    job_types: JobType[] = [];

    @Output() jobSaved = new EventEmitter<Job>();
    isNew = false
    editMode: boolean = true;
    workflowInputText: string = '{}';
    formError: string = '';



    constructor(@Inject(MAT_DIALOG_DATA) public data: Job,
                private jobService: JobService,
                private timeService: TimeService,
                private dialogRef: MatDialogRef<JobCardNewComponent> // Inject MatDialogRef

    ) {
        this.getJobTypes();

        if (!data) {
            this.job = new Job();
            this.workflowInputText = '{}';
            this.isNew = true;
            return;
        }
        this.job = data;
        if (this.job.run_at) this.job.run_at = this.localDateTime(this.job.run_at);
        this.workflowInputText = JSON.stringify(this.job.input || {}, null, 2);
    }


    saveJob() {
        if (this.inputEditor && !this.inputEditor.validate()) return;
        try {
            const parsed = JSON.parse(this.workflowInputText || '{}');
            if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
                throw new Error('Workflow input must be a JSON object');
            }
            this.job.input = parsed;
            this.formError = '';
        } catch (error) {
            this.formError = error instanceof Error ? error.message : 'Workflow input must be valid JSON';
            return;
        }
        this.jobService.saveJob(this.job).subscribe({
            next: job => {
                this.job = job;
                this.dialogRef.close(job);
                this.jobSaved.emit(this.job);
            },
            error: response => this.formError = response.error?.message || 'Job could not be saved.',
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

    onRevisionChange(revisionId: string) {
        const selectedType = this.job_types.find(type => type.revision_id === revisionId);
        if (selectedType) {
            this.job.job_type = selectedType.job_type;
            this.job.description = selectedType.description;
            this.job.workflow_revision_id = selectedType.revision_id;
            this.workflowInputText = JSON.stringify(exampleInput(selectedType.input_schema), null, 2);
        }
    }

    get selectedType(): JobType | undefined {
        return this.job_types.find(type => type.revision_id === this.job.workflow_revision_id)
            ?? this.job_types.find(type => type.job_type === this.job.job_type && type.active);
    }

    private localDateTime(value: string): string {
        const date = new Date(value);
        const part = (number: number) => String(number).padStart(2, '0');
        return `${date.getFullYear()}-${part(date.getMonth()+1)}-${part(date.getDate())}T${part(date.getHours())}:${part(date.getMinutes())}`;
    }
}
