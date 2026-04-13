import {Component, OnInit} from '@angular/core';
import {ScriptService} from '../../../services/script.service';
import {Script, ScriptParam} from '../../../models/script';
import {JobRun} from '../../../models/job-run';
import {JobRunLogComponent} from '../job-run-log/job-run-log.component';
import {MatDialog} from '@angular/material/dialog';
import {MatExpansionModule} from '@angular/material/expansion';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatCheckboxModule} from '@angular/material/checkbox';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {MatSelectModule} from '@angular/material/select';
import {FormsModule} from '@angular/forms';
import {NgForOf, NgIf} from '@angular/common';

interface ScriptFormValues {
    [paramName: string]: any;
}

@Component({
    selector: 'app-script-runner',
    standalone: true,
    imports: [
        MatExpansionModule,
        MatFormFieldModule,
        MatInputModule,
        MatCheckboxModule,
        MatButtonModule,
        MatIconModule,
        MatProgressSpinnerModule,
        MatSelectModule,
        FormsModule,
        NgForOf,
        NgIf,
    ],
    templateUrl: './script-runner.component.html',
    styleUrl: './script-runner.component.css',
})
export class ScriptRunnerComponent implements OnInit {
    scripts: Script[] = [];
    formValues: Map<string, ScriptFormValues> = new Map();
    reasonSelected: Map<string, string> = new Map();
    reasonFreeText: Map<string, string> = new Map();
    loading = true;
    runningScripts: Set<string> = new Set();

    private hiddenParams = new Set<string>();

    constructor(
        private scriptService: ScriptService,
        private dialog: MatDialog,
    ) {}

    ngOnInit() {
        this.scriptService.listScripts().subscribe({
            next: (scripts) => {
                this.scripts = scripts;
                for (const script of scripts) {
                    const values: ScriptFormValues = {};
                    for (const param of script.params) {
                        if (this.isHidden(param)) continue;
                        values[param.name] = this.getDefaultValue(param);
                    }
                    this.formValues.set(script.path, values);
                }
                this.loading = false;
            },
            error: () => {
                this.loading = false;
            },
        });
    }

    getVisibleParams(script: Script): ScriptParam[] {
        return script.params.filter(p => !this.isHidden(p));
    }

    isHidden(param: ScriptParam): boolean {
        return this.hiddenParams.has(param.name.toLowerCase());
    }

    isBoolean(param: ScriptParam): boolean {
        return param.type === 'boolean';
    }

    getDefaultValue(param: ScriptParam): any {
        if (param.name === 'TestRun') return false;
        if (param.name === 'DebugFlag') return true;
        if (param.type === 'boolean') return param.default ?? false;
        return param.default ?? '';
    }

    getFormValue(scriptPath: string, paramName: string): any {
        return this.formValues.get(scriptPath)?.[paramName];
    }

    isControlRoom(param: ScriptParam): boolean {
        return param.name.toLowerCase() === 'controlroom';
    }

    setFormValue(scriptPath: string, paramName: string, value: any): void {
        const values = this.formValues.get(scriptPath);
        if (values) {
            if (paramName.toLowerCase() === 'controlroom' && typeof value === 'string') {
                value = value.replace(/\D/g, '').slice(0, 3);
            }
            values[paramName] = value;
        }
    }

    hasInvalidParams(script: Script): boolean {
        const values = this.formValues.get(script.path);
        if (!values) return true;
        for (const param of script.params) {
            if (this.isControlRoom(param) && !/^\d{3}$/.test(values[param.name] ?? '')) {
                return true;
            }
        }
        // Reason is mandatory
        if (!this.hasValidReason(script)) {
            return true;
        }
        return false;
    }

    hasValidReason(script: Script): boolean {
        const selected = this.reasonSelected.get(script.path) ?? '';
        const freeText = this.reasonFreeText.get(script.path) ?? '';
        return selected.trim().length > 0 || freeText.trim().length > 0;
    }

    getScriptDisplayName(script: Script): string {
        return script.name.replace('.ps1', '');
    }

    runScript(script: Script): void {
        const values = this.formValues.get(script.path) ?? {};
        const params: Record<string, any> = {};

        for (const [key, value] of Object.entries(values)) {
            if (value !== '' && value !== null && value !== undefined) {
                params[key] = value;
            }
        }

        const reason = {
            selected: (this.reasonSelected.get(script.path) ?? '').trim() || null,
            freeText: (this.reasonFreeText.get(script.path) ?? '').trim() || null,
        };

        this.runningScripts.add(script.path);

        this.scriptService.runScript(script.path, params, reason).subscribe(response => {
            this.runningScripts.delete(script.path);
            if (response?.job_run_id) {
                const jobRun = new JobRun({
                    id: response.job_run_id as any,
                    name: script.name,
                    status: 'Started',
                    job_type: 'run_script',
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

    isRunning(script: Script): boolean {
        return this.runningScripts.has(script.path);
    }
}
