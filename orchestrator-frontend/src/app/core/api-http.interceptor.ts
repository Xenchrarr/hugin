import { HttpInterceptorFn, HttpErrorResponse, HttpResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, tap, throwError } from 'rxjs';
import { NotificationService } from '../services/notification.service';
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

    const showError = req.context.get(SHOW_ERROR);
    const showSuccess = req.context.get(SHOW_SUCCESS);
    const customSuccessMsg = req.context.get(SUCCESS_MESSAGE);
    const customErrorMsg = req.context.get(ERROR_MESSAGE);

    const corrId = getOrCreateCorrelationId();
    const reqWithCorr = req.clone({ setHeaders: { [CORR_HEADER]: corrId } });

    return next(reqWithCorr).pipe(
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
