import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-users-shell',
  standalone: true,
  imports: [RouterModule],
  templateUrl: './users-shell.component.html',
  styleUrl: './users-shell.component.scss',
})
export class UsersShellComponent {}
