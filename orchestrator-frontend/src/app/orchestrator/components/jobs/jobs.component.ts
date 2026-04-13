import {Component, OnInit} from '@angular/core';
import {MatCard, MatCardContent, MatCardTitle} from "@angular/material/card";
import {NgForOf, NgIf} from "@angular/common";
import {JobService} from "../../services/job.service";
import {MatButton} from "@angular/material/button";
import {Job} from "../../models/job";
import {JobType} from "../../models/job-type";
import {JobNavComponent} from "./job-nav/job-nav.component";
import {JobRunsComponent} from "./job-runs/job-runs.component";
import {JobSettingsNewComponent} from "./job-settings-new/job-settings-new.component";
import {ScriptRunnerComponent} from "./script-runner/script-runner.component";

@Component({
    selector: 'app-jobs',
    standalone: true,
    imports: [
        MatButton,
        JobNavComponent,
        NgIf,
        JobRunsComponent,
        JobSettingsNewComponent,
        ScriptRunnerComponent
    ],
    templateUrl: './jobs.component.html',
    styleUrl: './jobs.component.css'
})
export class JobsComponent implements OnInit{
    jobs: Job[] = [];
    job_types: JobType[] = [];

    current_page: string = '';

    constructor(private jobService: JobService) {
    }

    ngOnInit() {
        // this.jobService.getJobs().subscribe((jobs) => {
        //     this.jobs = jobs;
        // });
        //
        // this.jobService.getJobTypes().subscribe(job_types => {
        //     this.job_types = job_types;
        // });
    }

    onSiteSelected(site: string){
        this.current_page = site;
    }
}
