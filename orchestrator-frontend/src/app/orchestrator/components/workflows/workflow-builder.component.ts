import {CommonModule} from '@angular/common';
import {CdkDragDrop, DragDropModule, moveItemInArray} from '@angular/cdk/drag-drop';
import {Component, OnInit} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {ActivatedRoute, Router, RouterLink} from '@angular/router';
import {finalize, forkJoin, Observable} from 'rxjs';
import {
    JsonSchema, WorkflowBinding, WorkflowCondition, WorkflowDraft,
    WorkflowEditorStep, WorkflowIssue, WorkflowStepType,
} from '../../models/workflow';
import {WorkflowService} from '../../services/workflow.service';
import {formatWorkflowKey} from './shared/workflow-format';

interface InputField {name: string; schema: JsonSchema; required: boolean;}
interface SourceOption {value: string; label: string; conditional: boolean;}

@Component({
    selector: 'app-workflow-builder',
    standalone: true,
    imports: [CommonModule, DragDropModule, FormsModule, MatButtonModule, MatIconModule, RouterLink],
    templateUrl: './workflow-builder.component.html',
    styleUrl: './workflow-builder.component.scss',
})
export class WorkflowBuilderComponent implements OnInit {
    workflowKey = '';
    draft: WorkflowDraft | null = null;
    stepTypes: WorkflowStepType[] = [];
    revisions: WorkflowDraft[] = [];
    selectedIndex = -1;
    loading = true;
    busy = false;
    message = '';
    errorMessage = '';
    issues: WorkflowIssue[] = [];
    newKey = '';
    newName = '';
    newDescription = '';
    literalText: Record<string, string> = {};
    mergeSelections: Record<string, string[]> = {};
    conditionLiteral: Record<string, string> = {};

    constructor(
        private readonly route: ActivatedRoute,
        private readonly router: Router,
        private readonly api: WorkflowService,
    ) {}

    ngOnInit(): void {
        this.workflowKey = this.route.snapshot.paramMap.get('workflowKey') ?? '';
        if (!this.workflowKey) {
            this.api.listStepTypes().pipe(finalize(() => this.loading = false)).subscribe({
                next: types => this.stepTypes = types,
                error: () => this.errorMessage = 'The step catalog could not be loaded.',
            });
            return;
        }
        this.load();
    }

    get isNew(): boolean { return !this.workflowKey; }
    get editor() { return this.draft?.editor_definition; }
    get selectedStep(): WorkflowEditorStep | null {
        return this.editor?.steps[this.selectedIndex] ?? null;
    }
    get inputFields(): InputField[] {
        const schema = this.editor?.input_schema;
        const required = new Set(schema?.required ?? []);
        return Object.entries(schema?.properties ?? {}).map(([name, value]) => ({
            name, schema: value, required: required.has(name),
        }));
    }
    get selectedType(): WorkflowStepType | null {
        const step = this.selectedStep;
        return step ? this.stepTypes.find(item => item.key === step.step && item.version === step.step_version) ?? null : null;
    }
    get selectedInputs(): [string, JsonSchema][] {
        return Object.entries(this.selectedType?.input_schema.properties ?? {});
    }
    get selectedOutputs(): [string, JsonSchema][] {
        return Object.entries(this.selectedType?.output_schema.properties ?? {});
    }

    load(): void {
        this.loading = true;
        this.errorMessage = '';
        forkJoin({
            draft: this.api.draft(this.workflowKey),
            revisions: this.api.revisions(this.workflowKey),
            stepTypes: this.api.listStepTypes(),
        }).pipe(finalize(() => this.loading = false)).subscribe({
            next: result => {
                this.draft = result.draft;
                this.revisions = result.revisions;
                this.stepTypes = result.stepTypes;
                this.selectedIndex = result.draft.editor_definition.steps.length ? 0 : -1;
                this.hydrateEditorState();
            },
            error: error => this.errorMessage = error?.error?.message ?? 'The workflow draft could not be loaded.',
        });
    }

    create(): void {
        if (this.busy) return;
        this.busy = true;
        this.clearFeedback();
        this.api.create(this.newKey.trim(), this.newName.trim(), this.newDescription.trim())
            .pipe(finalize(() => this.busy = false)).subscribe({
                next: item => void this.router.navigate(['/workflows', item.key, 'edit']),
                error: error => this.errorMessage = error?.error?.message ?? 'The workflow could not be created.',
            });
    }

    addInput(): void {
        if (!this.editor) return;
        const properties = this.editor.input_schema.properties ??= {};
        let index = Object.keys(properties).length + 1;
        while (properties[`input_${index}`]) index++;
        properties[`input_${index}`] = {type: 'string', description: ''};
    }

    renameInput(field: InputField, name: string): void {
        if (!this.editor || name === field.name || !name) return;
        const properties = this.editor.input_schema.properties ??= {};
        if (properties[name]) return;
        delete properties[field.name];
        properties[name] = field.schema;
        const required = this.editor.input_schema.required ?? [];
        const index = required.indexOf(field.name);
        if (index >= 0) required[index] = name;
        for (const step of this.editor.steps) {
            for (const binding of Object.values(step.bindings)) {
                if (binding.source === 'workflow_input' && binding.path[0] === field.name) binding.path[0] = name;
            }
        }
    }

    setRequired(name: string, required: boolean): void {
        if (!this.editor) return;
        const values = this.editor.input_schema.required ??= [];
        const index = values.indexOf(name);
        if (required && index < 0) values.push(name);
        if (!required && index >= 0) values.splice(index, 1);
    }

    removeInput(name: string): void {
        if (!this.editor) return;
        delete this.editor.input_schema.properties?.[name];
        this.editor.input_schema.required = (this.editor.input_schema.required ?? []).filter(item => item !== name);
    }

    addStep(type: WorkflowStepType): void {
        if (!this.editor) return;
        const base = type.key.split('.').pop()?.replace(/[^a-z0-9_-]/g, '_') || 'step';
        let key = base;
        let suffix = 2;
        while (this.editor.steps.some(item => item.key === key)) key = `${base}_${suffix++}`;
        const bindings: Record<string, WorkflowBinding> = {};
        for (const name of type.input_schema.required ?? []) {
            bindings[name] = {source: 'literal', value: this.defaultValue(type.input_schema.properties?.[name])};
        }
        this.editor.steps.push({key, step: type.key, step_version: type.version, bindings, on_failure: 'stop'});
        this.selectedIndex = this.editor.steps.length - 1;
        this.hydrateStepState(this.editor.steps[this.selectedIndex]);
    }

    removeStep(index: number): void {
        if (!this.editor) return;
        const removed = this.editor.steps[index].key;
        this.editor.steps.splice(index, 1);
        for (const step of this.editor.steps) {
            for (const [name, binding] of Object.entries(step.bindings)) {
                if (this.bindingUsesStep(binding, removed)) delete step.bindings[name];
            }
        }
        this.selectedIndex = Math.min(index, this.editor.steps.length - 1);
    }

    drop(event: CdkDragDrop<WorkflowEditorStep[]>): void {
        if (!this.editor) return;
        moveItemInArray(this.editor.steps, event.previousIndex, event.currentIndex);
        this.selectedIndex = event.currentIndex;
    }

    binding(step: WorkflowEditorStep, input: string): WorkflowBinding | undefined { return step.bindings[input]; }
    sourceKind(step: WorkflowEditorStep, input: string): string { return step.bindings[input]?.source ?? 'none'; }

    setSource(step: WorkflowEditorStep, input: string, source: string, schema: JsonSchema): void {
        const id = this.controlId(step, input);
        if (source === 'none') { delete step.bindings[input]; return; }
        if (source === 'literal') {
            const value = this.defaultValue(schema);
            step.bindings[input] = {source: 'literal', value};
            this.literalText[id] = JSON.stringify(value, null, 2);
        } else if (source === 'workflow_input') {
            step.bindings[input] = {source: 'workflow_input', path: []};
        } else if (source === 'step_output') {
            step.bindings[input] = {source: 'step_output', step_key: '', path: []};
        } else {
            step.bindings[input] = {source: 'first_available', candidates: []};
            this.mergeSelections[id] = [];
        }
    }

    setWorkflowInput(step: WorkflowEditorStep, input: string, name: string): void {
        step.bindings[input] = {source: 'workflow_input', path: name ? [name] : []};
    }

    setStepOutput(step: WorkflowEditorStep, input: string, encoded: string): void {
        const [stepKey, ...path] = encoded.split('|');
        step.bindings[input] = {source: 'step_output', step_key: stepKey, path, optional: this.isConditional(stepKey)};
    }

    setMerge(step: WorkflowEditorStep, input: string, values: string[]): void {
        this.mergeSelections[this.controlId(step, input)] = values;
        step.bindings[input] = {source: 'first_available', candidates: values.map(encoded => {
            const [stepKey, ...path] = encoded.split('|');
            return {source: 'step_output', step_key: stepKey, path, optional: true};
        })};
    }

    updateLiteral(step: WorkflowEditorStep, input: string, text: string): void {
        this.literalText[this.controlId(step, input)] = text;
        try { step.bindings[input] = {source: 'literal', value: JSON.parse(text)}; } catch { /* surfaced by validation */ }
    }

    sourceOptions(step: WorkflowEditorStep, target?: JsonSchema): SourceOption[] {
        if (!this.editor) return [];
        const before = this.editor.steps.slice(0, this.editor.steps.indexOf(step));
        const options: SourceOption[] = [];
        for (const prior of before) {
            const type = this.stepTypes.find(item => item.key === prior.step && item.version === prior.step_version);
            if (this.compatible(type?.output_schema, target)) options.push({
                value: prior.key, label: `${prior.key} → entire output`,
                conditional: Boolean(prior.when) || prior.on_failure === 'continue',
            });
            for (const [name, schema] of Object.entries(type?.output_schema.properties ?? {})) {
                if (this.compatible(schema, target)) options.push({
                    value: `${prior.key}|${name}`, label: `${prior.key} → ${name}`,
                    conditional: Boolean(prior.when) || prior.on_failure === 'continue',
                });
            }
        }
        return options;
    }

    workflowInputs(target?: JsonSchema): InputField[] {
        return this.inputFields.filter(item => this.compatible(item.schema, target));
    }

    toggleCondition(step: WorkflowEditorStep, enabled: boolean): void {
        if (enabled) {
            const first = this.inputFields[0]?.name;
            step.when = {op: 'eq', left: {source: 'workflow_input', path: first ? [first] : []}, right: {source: 'literal', value: true}};
            this.conditionLiteral[step.key] = 'true';
        } else delete step.when;
    }

    setConditionSource(step: WorkflowEditorStep, encoded: string): void {
        if (!step.when) return;
        let operand;
        if (encoded.startsWith('input|')) operand = {source: 'workflow_input' as const, path: [encoded.slice(6)]};
        else { const [stepKey, ...path] = encoded.slice(5).split('|'); operand = {source: 'step_output' as const, step_key: stepKey, path}; }
        if (['exists', 'is_true', 'is_false'].includes(step.when.op)) step.when.value = operand;
        else step.when.left = operand;
    }

    conditionSource(step: WorkflowEditorStep): string {
        const operand = ['exists', 'is_true', 'is_false'].includes(step.when?.op ?? '') ? step.when?.value : step.when?.left;
        if (operand?.source === 'workflow_input') return `input|${operand.path[0] ?? ''}`;
        if (operand?.source === 'step_output') return `step|${operand.step_key}|${operand.path.join('|')}`;
        return '';
    }

    conditionSources(step: WorkflowEditorStep): SourceOption[] {
        return [
            ...this.inputFields.map(item => ({value: `input|${item.name}`, label: `Input → ${item.name}`, conditional: false})),
            ...this.sourceOptions(step).map(item => ({...item, value: `step|${item.value}`})),
        ];
    }

    setConditionOperator(step: WorkflowEditorStep, op: string): void {
        if (!step.when) return;
        const source = step.when.left ?? step.when.value ?? {source: 'literal' as const, value: true};
        step.when = ['exists', 'is_true', 'is_false'].includes(op)
            ? {op: op as WorkflowCondition['op'], value: source}
            : {op: op as WorkflowCondition['op'], left: source, right: {source: 'literal', value: true}};
        this.conditionLiteral[step.key] = 'true';
    }

    updateConditionLiteral(step: WorkflowEditorStep, text: string): void {
        this.conditionLiteral[step.key] = text;
        if (!step.when) return;
        try { step.when.right = {source: 'literal', value: JSON.parse(text)}; } catch { /* validation reports it */ }
    }

    save(): void { this.persist('save'); }
    validate(): void { this.persist('validate'); }
    publish(): void { this.persist('publish'); }

    clone(revision: WorkflowDraft): void {
        if (!this.draft || revision.version == null || this.busy) return;
        this.busy = true;
        this.clearFeedback();
        this.api.cloneRevision(this.workflowKey, revision.version, this.draft.lock_version)
            .pipe(finalize(() => this.busy = false)).subscribe({
                next: item => { this.draft = item; this.selectedIndex = item.editor_definition.steps.length ? 0 : -1; this.message = `Version ${revision.version} copied into the draft.`; this.hydrateEditorState(); },
                error: error => this.handleError(error, 'The revision could not be cloned.'),
            });
    }

    formatKey(value: string): string { return formatWorkflowKey(value); }
    controlId(step: WorkflowEditorStep, input: string): string { return `${step.key}:${input}`; }

    private persist(action: 'save' | 'validate' | 'publish'): void {
        if (!this.draft || !this.editor || this.busy) return;
        this.editor.description = this.draft.description;
        this.busy = true;
        this.clearFeedback();
        const request: Observable<unknown> = action === 'save'
            ? this.api.saveDraft(this.workflowKey, this.draft.name, this.draft.description, this.editor, this.draft.lock_version)
            : action === 'publish'
                ? this.api.publish(this.workflowKey, this.draft.name, this.draft.description, this.editor, this.draft.lock_version)
                : this.api.validate(this.workflowKey, this.editor);
        request.pipe(finalize(() => this.busy = false)).subscribe({
            next: (result: unknown) => {
                if (action === 'validate') this.message = 'The draft is valid and ready to publish.';
                else if (action === 'save') { this.draft = result as WorkflowDraft; this.message = 'Draft saved.'; }
                else { this.message = `Version ${(result as WorkflowDraft).version} published.`; this.load(); }
            },
            error: (error: any) => this.handleError(error, `The workflow could not be ${action === 'publish' ? 'published' : action === 'save' ? 'saved' : 'validated'}.`),
        });
    }

    private clearFeedback(): void { this.message = ''; this.errorMessage = ''; this.issues = []; }
    private handleError(error: any, fallback: string): void {
        this.errorMessage = error?.error?.message ?? fallback;
        this.issues = error?.error?.issues ?? [];
    }
    private defaultValue(schema?: JsonSchema): unknown {
        if (schema?.default !== undefined) return schema.default;
        const type = Array.isArray(schema?.type) ? schema?.type[0] : schema?.type;
        return type === 'boolean' ? false : type === 'integer' || type === 'number' ? 0 : type === 'array' ? [] : type === 'object' ? {} : '';
    }
    private compatible(source?: JsonSchema, target?: JsonSchema): boolean {
        const sourceType = Array.isArray(source?.type) ? source?.type[0] : source?.type;
        const targetType = Array.isArray(target?.type) ? target?.type[0] : target?.type;
        return !targetType || sourceType === targetType || (sourceType === 'integer' && targetType === 'number');
    }
    private isConditional(key: string): boolean {
        const step = this.editor?.steps.find(item => item.key === key);
        return Boolean(step?.when) || step?.on_failure === 'continue';
    }
    private bindingUsesStep(binding: WorkflowBinding, key: string): boolean {
        if (binding.source === 'step_output') return binding.step_key === key;
        return binding.source === 'first_available' && binding.candidates.some(item => this.bindingUsesStep(item, key));
    }
    private hydrateEditorState(): void {
        for (const step of this.editor?.steps ?? []) this.hydrateStepState(step);
    }
    private hydrateStepState(step: WorkflowEditorStep): void {
        for (const [input, binding] of Object.entries(step.bindings)) {
            const id = this.controlId(step, input);
            if (binding.source === 'literal') this.literalText[id] = JSON.stringify(binding.value, null, 2);
            if (binding.source === 'first_available') this.mergeSelections[id] = binding.candidates
                .filter((item): item is Extract<WorkflowBinding, {source: 'step_output'}> => item.source === 'step_output')
                .map(item => [item.step_key, ...item.path].join('|'));
        }
        const right = step.when?.right;
        if (right?.source === 'literal') this.conditionLiteral[step.key] = JSON.stringify(right.value);
    }
}
