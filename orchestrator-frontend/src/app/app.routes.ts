import { Routes } from '@angular/router';
import { AppShellComponent } from './components/app-shell/app-shell.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';


export const routes: Routes = [
    {
        path: '',
        component: AppShellComponent,
        children: [
            { path: '', redirectTo: 'scripts', pathMatch: 'full' },
            { path: 'dashboard', component: DashboardComponent },

            {
              path: '',
              loadChildren: () =>
                import('./orchestrator/orchestrator-module').then(m => m.OrchestratorModule),
            },

            { path: '**', redirectTo: 'scripts' },
        ],
    },
];
