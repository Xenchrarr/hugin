import { HttpContext } from '@angular/common/http';
import { SHOW_SUCCESS, SUCCESS_MESSAGE, SHOW_ERROR, ERROR_MESSAGE } from './api-context';

export function successContext(message: string) {
    return {
        context: new HttpContext()
            .set(SHOW_SUCCESS, true)
            .set(SUCCESS_MESSAGE, message)
            .set(SHOW_ERROR, true)
    };
}
