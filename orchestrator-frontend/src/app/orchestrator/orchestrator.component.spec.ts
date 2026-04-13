import { TestBed } from '@angular/core/testing';
import { OrchestratorComponent } from './orchestrator.component';

describe('OrchestratorComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OrchestratorComponent],
    }).compileComponents();
  });

  it('should create the component', () => {
    const fixture = TestBed.createComponent(OrchestratorComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it(`should have the 'orchestrator' title`, () => {
    const fixture = TestBed.createComponent(OrchestratorComponent);
    const app = fixture.componentInstance;
    expect(app.title).toEqual('orchestrator');
  });
});
