import { ComponentFixture, TestBed } from '@angular/core/testing';

import { JobSettingsNewComponent } from './job-settings-new.component';

describe('JobSettingsNewComponent', () => {
  let component: JobSettingsNewComponent;
  let fixture: ComponentFixture<JobSettingsNewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobSettingsNewComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(JobSettingsNewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
