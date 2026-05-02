import { HttpInterceptorFn, HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, tap, throwError } from 'rxjs';
import { Router } from '@angular/router';
import { NotificationService } from '../services/notification.service';
import { AuthService } from '../auth/auth.service';
import { SHOW_SUCCESS, SUCCESS_MESSAGE, SHOW_ERROR, ERROR_MESSAGE } from './api-context';

const CORR_HEADER = 'X-Correlation-Id';

function getOrCreateCorrelationId(): string {
  const key = 'corrId';
  const existing = sessionStorage.getItem(key);
  if (existing) return existing;

  const id =
    (globalThis.crypto?.randomUUID?.() ?? `corr_${Date.now()}_${Math.random().toString(16).slice(2)}`);
  sessionStorage.setItem(key, id);
  return id;
}

export const apiHttpInterceptorFn: HttpInterceptorFn = (req, next) => {
    const notify = inject(NotificationService);
    const auth = inject(AuthService);
    const router = inject(Router);

    const showError = req.context.get(SHOW_ERROR);
    const showSuccess = req.context.get(SHOW_SUCCESS);
    const customSuccessMsg = req.context.get(SUCCESS_MESSAGE);
    const customErrorMsg = req.context.get(ERROR_MESSAGE);

    const corrId = getOrCreateCorrelationId();

    // Attach JWT token to all requests except the login endpoint
    const token = auth.getToken();
    const isLoginEndpoint = req.url.includes('/api/auth/login');
    const headers: Record<string, string> = { [CORR_HEADER]: corrId };
    if (token && !isLoginEndpoint) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const reqWithHeaders = req.clone({ setHeaders: headers });

    return next(reqWithHeaders).pipe(
        tap(evt => {
            if (
                showSuccess &&
                evt instanceof HttpResponse &&
                ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)
            ) {
                notify.success(customSuccessMsg ?? 'Lagret');
            }
        }),
        catchError((err: HttpErrorResponse) => {
            if (err.status === 401 && !isLoginEndpoint) {
                notify.error('Sesjonen har utløpt. Vennligst logg inn igjen.');
                auth.logout();
                router.navigateByUrl('/login');
            }

            if (showError) {
                const msg =
                    customErrorMsg ??
                    extractErrorMessage(err) ??
                    'Noe gikk galt. Prøv igjen.';
                notify.error(msg);
            }

            return throwError(() => err);
        })
    );
};

function extractErrorMessage(err: HttpErrorResponse): string | null {
    const e = err.error;
    if (!e) return null;
    if (typeof e === 'string') return e;
    if (e.message) return e.message;
    if (e.error) return e.error;
    if (Array.isArray(e.errors) && e.errors.length) return e.errors[0];
    return null;
}
