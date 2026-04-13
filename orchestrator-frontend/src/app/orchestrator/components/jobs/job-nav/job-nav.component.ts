import {AfterViewInit, Component, EventEmitter, OnInit, Output} from '@angular/core';

@Component({
  selector: 'app-job-nav',
  standalone: true,
  imports: [],
  templateUrl: './job-nav.component.html',
  styleUrl: './job-nav.component.css'
})
export class JobNavComponent implements AfterViewInit{
    selectedSite = '';

    @Output() siteSelected = new EventEmitter<string>();



    selectSite(site: string) {
        this.selectedSite = site;
        this.siteSelected.emit(site);
    }

    ngAfterViewInit(): void {
        // this.selectSite("job_runs")
    }
}
