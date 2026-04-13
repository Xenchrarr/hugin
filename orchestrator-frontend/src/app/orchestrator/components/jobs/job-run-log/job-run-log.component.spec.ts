import { ComponentFixture, TestBed } from '@angular/core/testing';

import { JobRunLogComponent } from './job-run-log.component';

describe('JobRunLogComponent', () => {
  let component: JobRunLogComponent;
  let fixture: ComponentFixture<JobRunLogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobRunLogComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(JobRunLogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
