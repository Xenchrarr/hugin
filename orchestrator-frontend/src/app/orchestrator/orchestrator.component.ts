import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-orchestrator-root',
  standalone: true,
  imports: [RouterOutlet],
  templateUrl: './orchestrator.component.html',
  styleUrl: './orchestrator.component.css'
})
export class OrchestratorComponent {
  title = 'orchestrator';
}
