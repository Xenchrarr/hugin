import {Component, OnInit} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatIconModule} from '@angular/material/icon';
import {MatInputModule} from '@angular/material/input';
import {RouterLink} from '@angular/router';
import {finalize, forkJoin} from 'rxjs';
import {WorkflowDefinition, WorkflowStepType} from '../../models/workflow';
import {WorkflowService} from '../../services/workflow.service';
import {formatWorkflowKey} from './shared/workflow-format';

@Component({
    selector: 'app-workflows',
    standalone: true,
    imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatIconModule, MatInputModule, RouterLink],
    templateUrl: './workflows.component.html',
    styleUrl: './workflows.component.scss',
})
export class WorkflowsComponent implements OnInit {
    workflows: WorkflowDefinition[] = [];
    stepTypes: WorkflowStepType[] = [];
    query = '';
    loading = true;
    errorMessage = '';

    constructor(private readonly workflowsApi: WorkflowService) {}

    ngOnInit(): void { this.load(); }

    get visibleWorkflows(): WorkflowDefinition[] {
        const query = this.query.toLowerCase().trim();
        return this.workflows.filter(workflow => !query || [workflow.key, workflow.description, ...workflow.steps.map(step => step.step)].join(' ').toLowerCase().includes(query));
    }

    get totalSteps(): number { return this.workflows.reduce((total, workflow) => total + workflow.steps.length, 0); }
    get conditionalSteps(): number { return this.workflows.reduce((total, workflow) => total + workflow.steps.filter(step => step.run_if).length, 0); }

    load(): void {
        this.loading = true;
        this.errorMessage = '';
        forkJoin({workflows: this.workflowsApi.list(), stepTypes: this.workflowsApi.listStepTypes()})
            .pipe(finalize(() => this.loading = false))
            .subscribe({
                next: ({workflows, stepTypes}) => { this.workflows = workflows.sort((a, b) => a.key.localeCompare(b.key)); this.stepTypes = stepTypes; },
                error: () => this.errorMessage = 'Workflow definitions could not be loaded.',
            });
    }

    formatKey(value: string): string { return formatWorkflowKey(value); }
}
