import { TestBed } from '@angular/core/testing';

import { JobRunService } from './job-run.service';

describe('JobRunsService', () => {
  let service: JobRunService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(JobRunService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
