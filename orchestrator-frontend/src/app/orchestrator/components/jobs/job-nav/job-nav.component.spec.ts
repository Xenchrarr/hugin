import { ComponentFixture, TestBed } from '@angular/core/testing';

import { JobNavComponent } from './job-nav.component';

describe('JobNavComponent', () => {
  let component: JobNavComponent;
  let fixture: ComponentFixture<JobNavComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [JobNavComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(JobNavComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
