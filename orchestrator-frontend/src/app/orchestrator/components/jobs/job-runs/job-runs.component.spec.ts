import { ComponentFixture, TestBed } from '@angular/core/testing';

import { JobRunsComponent } from './job-runs.component';

describe('JobRunsComponent', () => {
  let component: JobRunsComponent;
  let fixture: ComponentFixture<JobRunsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobRunsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(JobRunsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
