
import { HttpContextToken } from '@angular/common/http';

export const SHOW_SUCCESS = new HttpContextToken<boolean>(() => false);
export const SUCCESS_MESSAGE = new HttpContextToken<string | null>(() => null);

export const SHOW_ERROR = new HttpContextToken<boolean>(() => true);
export const ERROR_MESSAGE = new HttpContextToken<string | null>(() => null);
