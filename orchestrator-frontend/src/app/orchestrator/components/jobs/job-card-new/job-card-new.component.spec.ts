import { ComponentFixture, TestBed } from '@angular/core/testing';

import { JobCardNewComponent } from './job-card-new.component';

describe('JobCardNewComponent', () => {
  let component: JobCardNewComponent;
  let fixture: ComponentFixture<JobCardNewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobCardNewComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(JobCardNewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
