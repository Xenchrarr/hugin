import { Routes } from '@angular/router';
import { AppShellComponent } from './components/app-shell/app-shell.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { LoginComponent } from './auth/login/login.component';
import { authGuard } from './auth/auth.guard';


export const routes: Routes = [
    {
        path: 'login',
        component: LoginComponent,
    },
    {
        path: '',
        component: AppShellComponent,
        canActivate: [authGuard],
        children: [
            { path: '', redirectTo: 'scripts', pathMatch: 'full' },
            { path: 'dashboard', component: DashboardComponent },

            {
              path: 'users',
              loadChildren: () =>
                import('./users/users-module').then(m => m.UsersModule),
            },

            {
              path: '',
              loadChildren: () =>
                import('./orchestrator/orchestrator-module').then(m => m.OrchestratorModule),
            },

            { path: '**', redirectTo: 'scripts' },
        ],
    },
];
