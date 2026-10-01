import { Component } from '@angular/core';
import { ScriptRunnerComponent } from '../jobs/script-runner/script-runner.component';

@Component({
    selector: 'app-scripts-page',
    standalone: true,
    imports: [ScriptRunnerComponent],
    templateUrl: './scripts-page.component.html',
    styleUrl: './scripts-page.component.scss',
})
export class ScriptsPageComponent {}
