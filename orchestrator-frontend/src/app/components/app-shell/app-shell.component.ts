import { Component } from '@angular/core';
import { MatListModule } from "@angular/material/list";
import { RouterModule } from "@angular/router";
import { MatToolbarModule } from "@angular/material/toolbar";
import { MatSidenavModule } from "@angular/material/sidenav";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";

@Component({
  selector: 'app-shell-component',
  standalone: true,
  imports: [MatListModule, RouterModule, MatToolbarModule, MatSidenavModule, MatIconModule, MatButtonModule],
  templateUrl: './app-shell.component.html',
  styleUrls: ['./app-shell.component.scss'],
})
export class AppShellComponent {
  collapsed = false;

  toggleCollapsed() {
    this.collapsed = !this.collapsed;
  }
}
