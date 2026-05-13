import {Component, Input} from '@angular/core';
import {NgFor, NgIf} from '@angular/common';
import {MatIconButton} from '@angular/material/button';
import {MatIcon} from '@angular/material/icon';
import {CalendarEvent} from '../../../models/ical-source';

interface WeekDay {
    date: Date;
    label: string;
    shortDate: string;
    isToday: boolean;
    events: CalendarEvent[];
}

@Component({
    selector: 'app-week-view',
    standalone: true,
    imports: [NgFor, NgIf, MatIconButton, MatIcon],
    templateUrl: './week-view.component.html',
    styleUrl: './week-view.component.scss',
})
export class WeekViewComponent {
    weekDays: WeekDay[] = [];
    weekLabel = '';
    private _events: CalendarEvent[] = [];
    private _weekStart: Date = this._getMonday(new Date());

    @Input() set events(events: CalendarEvent[]) {
        this._events = events;
        this._buildWeek();
    }

    prevWeek() {
        this._weekStart = new Date(this._weekStart);
        this._weekStart.setDate(this._weekStart.getDate() - 7);
        this._buildWeek();
    }

    nextWeek() {
        this._weekStart = new Date(this._weekStart);
        this._weekStart.setDate(this._weekStart.getDate() + 7);
        this._buildWeek();
    }

    formatTime(event: CalendarEvent): string {
        if (event.all_day) return 'All day';
        const d = new Date(event.start);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', hour12: false});
    }

    private _buildWeek() {
        const today = new Date();
        const days: WeekDay[] = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(this._weekStart);
            d.setDate(d.getDate() + i);
            const key = this._dateKey(d);
            days.push({
                date: d,
                label: d.toLocaleDateString([], {weekday: 'short'}),
                shortDate: d.toLocaleDateString([], {month: 'short', day: 'numeric'}),
                isToday: d.toDateString() === today.toDateString(),
                events: this._events.filter(e => e.start.substring(0, 10) === key),
            });
        }
        this.weekDays = days;

        const end = new Date(this._weekStart);
        end.setDate(end.getDate() + 6);
        this.weekLabel = this._weekStart.toLocaleDateString([], {month: 'short', day: 'numeric'})
            + ' – ' + end.toLocaleDateString([], {month: 'short', day: 'numeric', year: 'numeric'});
    }

    private _getMonday(d: Date): Date {
        const day = d.getDay();
        const diff = (day === 0 ? -6 : 1 - day);
        const monday = new Date(d);
        monday.setDate(d.getDate() + diff);
        monday.setHours(0, 0, 0, 0);
        return monday;
    }

    private _dateKey(d: Date): string {
        return d.toISOString().substring(0, 10);
    }
}
