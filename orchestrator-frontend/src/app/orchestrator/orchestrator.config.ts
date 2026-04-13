import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './orchestrator.routes';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import {DatePipe} from "@angular/common";

export const orchestratorConfig: ApplicationConfig = {
  providers: [provideZoneChangeDetection({ eventCoalescing: true }), provideRouter(routes), provideAnimationsAsync(), DatePipe]
};
