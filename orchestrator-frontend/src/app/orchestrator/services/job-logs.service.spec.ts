import { TestBed } from '@angular/core/testing';

import { JobLogsService } from './job-logs.service';

describe('JobLogsService', () => {
  let service: JobLogsService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(JobLogsService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
