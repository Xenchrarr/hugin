import { Component, inject } from '@angular/core';
import { Router } from "@angular/router";
import { MatListModule } from "@angular/material/list";
import { RouterModule } from "@angular/router";
import { MatToolbarModule } from "@angular/material/toolbar";
import { MatSidenavModule } from "@angular/material/sidenav";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatDividerModule } from "@angular/material/divider";
import { AsyncPipe } from "@angular/common";
import { AuthService } from "../../auth/auth.service";
import { environment } from "../../../environments/environment";

@Component({
  selector: 'app-shell-component',
  standalone: true,
  imports: [MatListModule, RouterModule, MatToolbarModule, MatSidenavModule, MatIconModule, MatButtonModule, MatDividerModule, AsyncPipe],
  templateUrl: './app-shell.component.html',
  styleUrls: ['./app-shell.component.scss'],
})
export class AppShellComponent {
  collapsed = false;
  readonly isProd = environment.production;

  constructor(public auth: AuthService, private router: Router) {}

  get username(): string | null {
    return this.auth.currentUser?.username ?? null;
  }

  toggleCollapsed() {
    this.collapsed = !this.collapsed;
  }

  logout(): void {
    this.auth.logout();
    this.router.navigateByUrl('/login');
  }
}
