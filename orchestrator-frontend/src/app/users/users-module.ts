import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Routes } from '@angular/router';
import { UsersShellComponent } from './users-shell.component';
import { routes as usersChildRoutes } from './users.routes';

const routes: Routes = [
  {
    path: '',
    component: UsersShellComponent,
    children: usersChildRoutes,
  },
];

@NgModule({
  imports: [
    CommonModule,
    RouterModule.forChild(routes),
  ],
})
export class UsersModule { }
