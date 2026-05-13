export class IcalSource {
    id: number = 0;
    name: string = '';
    url: string = '';
    enabled: boolean = true;
    color: string = '#1976d2';
    created_at: string | undefined = undefined;
    updated_at: string | undefined = undefined;

    constructor(init?: Partial<IcalSource>) {
        Object.assign(this, init);
    }
}

export interface CalendarEvent {
    start: string;
    end: string;
    summary: string;
    calendar_name: string;
    all_day: boolean;
    source_name: string;
    source_color: string;
    source_url?: string;
}
