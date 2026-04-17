export class Reminder {
    id: number = 0;
    title: string = '';
    message: string = '';
    due_at: string = '';
    recurrence: string | null = null;
    status: string = 'active';
    recipient_ids: number[] | null = null;
    created_by: string = 'frontend';
    scheduler_job_id: string | null = null;
    created_at: string | undefined = undefined;
    updated_at: string | undefined = undefined;

    constructor(init?: Partial<Reminder>) {
        Object.assign(this, init);
    }
}

export class NotificationSetting {
    id: number = 0;
    channel: string = '';
    enabled: boolean = true;
    config: Record<string, any> = {};
    user_label: string = '';
    created_at: string | undefined = undefined;
    updated_at: string | undefined = undefined;

    constructor(init?: Partial<NotificationSetting>) {
        Object.assign(this, init);
    }
}

export class ReminderHistory {
    id: number = 0;
    reminder_id: number = 0;
    action: string = '';
    channel: string = '';
    detail: string = '';
    created_at: string | undefined = undefined;

    constructor(init?: Partial<ReminderHistory>) {
        Object.assign(this, init);
    }
}
