import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Routes } from '@angular/router';
import { OrchestratorComponent } from './orchestrator.component';
import { routes as orchestratorChildRoutes } from './orchestrator.routes';

const routes: Routes = [
  {
    path: '',
    component: OrchestratorComponent,
    children: orchestratorChildRoutes,
  },
];

@NgModule({
  imports: [
    CommonModule,
    RouterModule.forChild(routes),
  ],
})
export class OrchestratorModule { }
