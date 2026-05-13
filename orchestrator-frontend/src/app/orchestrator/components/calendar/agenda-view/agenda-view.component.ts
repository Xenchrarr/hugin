import {Component, Input} from '@angular/core';
import {DatePipe, NgFor, NgIf} from '@angular/common';
import {MatChip, MatChipSet} from '@angular/material/chips';
import {CalendarEvent} from '../../../models/ical-source';

interface DayGroup {
    label: string;
    date: Date;
    events: CalendarEvent[];
}

@Component({
    selector: 'app-agenda-view',
    standalone: true,
    imports: [NgFor, NgIf, DatePipe, MatChip, MatChipSet],
    templateUrl: './agenda-view.component.html',
    styleUrl: './agenda-view.component.scss',
})
export class AgendaViewComponent {
    days: DayGroup[] = [];

    @Input() set events(events: CalendarEvent[]) {
        this.days = this._groupByDay(events);
    }

    isToday(date: Date): boolean {
        const now = new Date();
        return date.toDateString() === now.toDateString();
    }

    formatTime(event: CalendarEvent): string {
        if (event.all_day) return 'All day';
        const d = new Date(event.start);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', hour12: false});
    }

    private _groupByDay(events: CalendarEvent[]): DayGroup[] {
        const map = new Map<string, DayGroup>();
        for (const event of events) {
            const dateKey = event.start.substring(0, 10);
            if (!map.has(dateKey)) {
                map.set(dateKey, {label: this._dayLabel(dateKey), date: new Date(dateKey + 'T00:00:00'), events: []});
            }
            map.get(dateKey)!.events.push(event);
        }
        return Array.from(map.values()).sort((a, b) => a.date.getTime() - b.date.getTime());
    }

    private _dayLabel(dateKey: string): string {
        const d = new Date(dateKey + 'T00:00:00');
        const now = new Date();
        const tomorrow = new Date(now);
        tomorrow.setDate(now.getDate() + 1);
        if (d.toDateString() === now.toDateString()) return 'Today';
        if (d.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
        return d.toLocaleDateString([], {weekday: 'long', month: 'short', day: 'numeric'});
    }
}
