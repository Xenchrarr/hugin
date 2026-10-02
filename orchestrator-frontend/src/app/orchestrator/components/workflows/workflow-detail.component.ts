import {JsonPipe} from '@angular/common';
import {Component, OnInit, ViewChild} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {ActivatedRoute, Router, RouterLink} from '@angular/router';
import {finalize} from 'rxjs';
import {WorkflowDefinition, WorkflowStep} from '../../models/workflow';
import {WorkflowService} from '../../services/workflow.service';
import {exampleInput, formatWorkflowKey} from './shared/workflow-format';
import {WorkflowInputEditorComponent} from './shared/workflow-input-editor.component';

@Component({
    selector: 'app-workflow-detail',
    standalone: true,
    imports: [JsonPipe, MatButtonModule, MatIconModule, RouterLink, WorkflowInputEditorComponent],
    templateUrl: './workflow-detail.component.html',
    styleUrl: './workflow-detail.component.scss',
})
export class WorkflowDetailComponent implements OnInit {
    @ViewChild(WorkflowInputEditorComponent) inputEditor?: WorkflowInputEditorComponent;
    workflow: WorkflowDefinition | null = null;
    inputText = '{}';
    errorMessage = '';
    runError = '';
    loading = true;
    running = false;
    expandedStep = 0;
    showRawSchema = false;

    constructor(private readonly route: ActivatedRoute, private readonly router: Router, private readonly api: WorkflowService) {}

    ngOnInit(): void {
        const key = this.route.snapshot.paramMap.get('workflowKey') ?? '';
        this.api.get(key).pipe(finalize(() => this.loading = false)).subscribe({
            next: workflow => { this.workflow = workflow; this.inputText = JSON.stringify(exampleInput(workflow.input_schema), null, 2); },
            error: () => this.errorMessage = 'This workflow definition could not be loaded.',
        });
    }

    get title(): string { return this.workflow ? formatWorkflowKey(this.workflow.key) : 'Workflow'; }
    get requiredInputCount(): number { return this.workflow?.input_schema.required?.length ?? 0; }
    get conditionalStepCount(): number { return this.workflow?.steps.filter(step => step.when).length ?? 0; }
    get continueStepCount(): number { return this.workflow?.steps.filter(step => step.on_failure === 'continue').length ?? 0; }
    get inputFields(): [string, unknown][] { return Object.entries(this.workflow?.input_schema.properties ?? {}); }
    formatKey(value: string): string { return formatWorkflowKey(value); }
    toggleStep(index: number): void { this.expandedStep = this.expandedStep === index ? -1 : index; }
    stepBadges(step: WorkflowStep): string[] { return [step.when ? 'Conditional' : '', step.on_failure === 'continue' ? 'Continues on error' : ''].filter(Boolean); }
    schemaType(value: unknown): string { const schema = value as {type?: string | string[]}; return Array.isArray(schema.type) ? schema.type.join(' / ') : schema.type ?? 'any'; }
    schemaDescription(value: unknown): string { return (value as {description?: string}).description ?? 'No description provided.'; }
    resetInput(): void { if (this.workflow) { this.inputText = JSON.stringify(exampleInput(this.workflow.input_schema), null, 2); this.runError = ''; } }

    run(): void {
        if (!this.workflow || this.running || !this.inputEditor?.validate()) return;
        let input: Record<string, unknown>;
        try { input = JSON.parse(this.inputText); } catch { this.runError = 'Input must be valid JSON.'; return; }
        this.running = true;
        this.runError = '';
        this.api.execute(this.workflow.key, input).pipe(finalize(() => this.running = false)).subscribe({
            next: result => void this.router.navigate(['/executions', result.job_run_id]),
            error: error => this.runError = error?.error?.message ?? 'Workflow could not be started.',
        });
    }
}
