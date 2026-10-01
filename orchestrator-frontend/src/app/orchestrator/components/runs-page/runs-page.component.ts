import { Component } from '@angular/core';
import { JobRunsComponent } from '../jobs/job-runs/job-runs.component';

@Component({
    selector: 'app-runs-page',
    standalone: true,
    imports: [JobRunsComponent],
    templateUrl: './runs-page.component.html',
    styleUrl: './runs-page.component.scss',
})
export class RunsPageComponent {}
