import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UpcomingJobsComponent } from './upcoming-jobs.component';

describe('UpcommingJobsComponent', () => {
  let component: UpcomingJobsComponent;
  let fixture: ComponentFixture<UpcomingJobsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UpcomingJobsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(UpcomingJobsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
