import { Component } from '@angular/core';
import { JobRunsComponent } from '../jobs/job-runs/job-runs.component';

@Component({
    selector: 'app-runs-page',
    standalone: true,
    imports: [JobRunsComponent],
    template: `
        <h1>Runs</h1>
        <app-job-runs></app-job-runs>
    `,
})
export class RunsPageComponent {}
