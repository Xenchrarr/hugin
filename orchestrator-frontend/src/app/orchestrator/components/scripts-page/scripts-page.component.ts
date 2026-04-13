import { Component } from '@angular/core';
import { ScriptRunnerComponent } from '../jobs/script-runner/script-runner.component';

@Component({
    selector: 'app-scripts-page',
    standalone: true,
    imports: [ScriptRunnerComponent],
    template: `
        <h1>Scripts</h1>
        <app-script-runner></app-script-runner>
    `,
})
export class ScriptsPageComponent {}
