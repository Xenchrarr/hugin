import { Injectable } from '@angular/core';
import {DatePipe} from "@angular/common";

@Injectable({
    providedIn: 'root'
})
export class TimeService {

    constructor(private datePipe: DatePipe) { }

    formatDate(date1: string | undefined): string {
        if (!date1) {
            return '';
        }
        return this.formatInNorwegianTimezone(new Date(date1));
    }

    formatNextJobDate(date1: string | undefined): string {
        if (!date1) {
            return '';
        }
        return this.formatInNorwegianTimezone(new Date(date1));
    }

    private formatInNorwegianTimezone(date: Date): string {
        const formatter = new Intl.DateTimeFormat('en-US', {
            timeZone: 'Europe/Oslo',
            weekday: 'long',
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        const parts = formatter.formatToParts(date);
        const get = (type: string) => parts.find(p => p.type === type)?.value ?? '';

        return `${get('weekday')} ${get('day')}.${get('month')}.${get('year')} ${get('hour')}:${get('minute')}:${get('second')}`;
    }

}
