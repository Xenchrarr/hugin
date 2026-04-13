import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import {FooterComponent} from "./components/footer/footer.component";
import {NavBarComponent} from "./components/nav-bar/nav-bar.component";

@Component({
  selector: 'app-orchestrator-root',
  standalone: true,
  imports: [RouterOutlet, FooterComponent, NavBarComponent],
  templateUrl: './orchestrator.component.html',
  styleUrl: './orchestrator.component.css'
})
export class OrchestratorComponent {
  title = 'orchestrator';
}
