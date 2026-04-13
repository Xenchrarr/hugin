import {Component, OnInit} from '@angular/core';
import {JobService} from "../../../services/job.service";
import {Job} from "../../../models/job";
import {JobApi} from "../../../models/job-api";
import {NgForOf} from "@angular/common";
import {TimeService} from "../../../services/time.service";
import {MatButton, MatIconButton} from "@angular/material/button";

@Component({
    selector: 'app-upcoming-jobs',
    standalone: true,
    imports: [
        NgForOf,
        MatIconButton,
        MatButton
    ],
    templateUrl: './upcoming-jobs.component.html',
    styleUrl: './upcoming-jobs.component.css'
})
export class UpcomingJobsComponent implements OnInit {

    jobs: JobApi[] = []
    currentPage = 1; // Current page
    itemsPerPage = 5; // Number of jobs per page


    constructor(private jobService: JobService,
                private timeService: TimeService) {
    }

    ngOnInit(): void {
        this.getJobs()
        setInterval(() => {
            this.getJobs()
        }, 60000)
    }

    getJobs() {
        this.jobService.getJobsApi().subscribe(data => {
            this.jobs = data;
            // console.log(this.jobs)
            //
            // for (let i = 0; i < this.jobs.length; i++) {
            //
            //     for (let i = 0; i < this.jobs.length; i++) {
            //         const existingJob = this.jobs.find(job => job.job_id === data[i].job_id); // Find the job with same jobid
            //         if (existingJob) {
            //             existingJob.next_run_time = data[i].next_run_time; // Update the time of the job
            //             console.log("updated")
            //         }
            //     }
            // }
        })


    }

    getFormattedDate(date: string): string {
        return this.timeService.formatNextJobDate(date);
    }

    get paginatedJobs() {
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = startIndex + this.itemsPerPage;
        return this.jobs.slice(startIndex, endIndex);
    }

    get totalPages() {
        return Math.ceil(this.jobs.length / this.itemsPerPage);
    }

    changePage(page: number) {
        this.currentPage = page;
    }

}
