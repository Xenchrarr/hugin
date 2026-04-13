import {
    ApplicationConfig, provideBrowserGlobalErrorListeners,
    provideZoneChangeDetection, provideZonelessChangeDetection
} from '@angular/core';
import {provideRouter} from '@angular/router';
import 'zone.js';
import {routes} from './app.routes';
import {HTTP_INTERCEPTORS, provideHttpClient, withInterceptors} from '@angular/common/http';
import {apiHttpInterceptorFn} from './core/api-http.interceptor';

import {DatePipe, registerLocaleData} from "@angular/common";
import localeNb from '@angular/common/locales/nb';
import {provideAnimations} from '@angular/platform-browser/animations';
registerLocaleData(localeNb);

export const appConfig: ApplicationConfig = {
    providers: [
        DatePipe,
        provideBrowserGlobalErrorListeners(),
        provideRouter(routes),
        provideAnimations(),
        provideHttpClient(withInterceptors([apiHttpInterceptorFn])),
        provideZoneChangeDetection({
            eventCoalescing: true,
            runCoalescing: true})
        ],

};
