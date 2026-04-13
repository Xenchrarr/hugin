import {Component} from '@angular/core';
import {RouterLink, RouterLinkActive} from '@angular/router';
import {environment} from "../../../../environments/environment";
import {ConnectionStatusComponent} from "./connection-status/connection-status.component";
import {UpcomingJobsComponent} from "./upcoming-jobs/upcoming-jobs.component";

@Component({
    selector: 'app-nav-bar',
    templateUrl: './nav-bar.component.html',
    styleUrls: ['./nav-bar.component.css'],
    standalone: true,
    imports: [
        RouterLink,
        RouterLinkActive,
        ConnectionStatusComponent,
        UpcomingJobsComponent,
    ],
})
export class NavBarComponent {
    isProd = environment.production;
}
