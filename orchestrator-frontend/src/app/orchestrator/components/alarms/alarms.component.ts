import {CommonModule} from '@angular/common';
import {Component, OnInit} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatCardModule} from '@angular/material/card';
import {MatCheckboxModule} from '@angular/material/checkbox';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatIconModule} from '@angular/material/icon';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {MatSlideToggleModule} from '@angular/material/slide-toggle';
import {Alarm, AlarmOccurrence} from '../../models/alarm';
import {AlarmService} from '../../services/alarm.service';

@Component({
  selector: 'app-alarms', standalone: true,
  imports: [CommonModule, FormsModule, MatButtonModule, MatCardModule, MatCheckboxModule,
    MatFormFieldModule, MatIconModule, MatInputModule, MatSelectModule, MatSlideToggleModule],
  templateUrl: './alarms.component.html', styleUrl: './alarms.component.scss',
})
export class AlarmsComponent implements OnInit {
  alarms: Alarm[] = [];
  occurrences: AlarmOccurrence[] = [];
  editingId: number | null = null;
  busy = false;
  message = '';
  voiceReady: boolean | null = null;
  readonly days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  form = this.blank();

  constructor(private service: AlarmService) {}
  ngOnInit(): void { this.load(); this.checkVoice(); }

  blank(): Partial<Alarm> {
    const next = new Date(Date.now() + 3600000);
    next.setSeconds(0, 0);
    return {label: 'Wake up', enabled: true, schedule_type: 'once',
      scheduled_at: this.localDateTime(next), local_time: '07:00', weekdays: [0,1,2,3,4],
      timezone: 'Europe/Oslo', ring_seconds: 20, max_attempts: 3,
      retry_interval_seconds: 120, sms_fallback: true};
  }

  load(): void { this.service.list().subscribe(rows => this.alarms = rows); }
  checkVoice(): void {
    this.service.voiceHealth().subscribe({next: x => this.voiceReady = !!x.ready, error: () => this.voiceReady = false});
  }
  edit(alarm: Alarm): void {
    this.editingId = alarm.id;
    this.form = {...alarm, weekdays: [...(alarm.weekdays ?? [])],
      scheduled_at: alarm.scheduled_at ? this.localDateTime(new Date(alarm.scheduled_at)) : null};
    this.loadHistory(alarm.id);
  }
  reset(): void { this.editingId = null; this.form = this.blank(); this.occurrences = []; }
  toggleDay(day: number): void {
    const selected = [...(this.form.weekdays ?? [])];
    const index = selected.indexOf(day);
    index >= 0 ? selected.splice(index, 1) : selected.push(day);
    this.form.weekdays = selected.sort();
  }
  hasDay(day: number): boolean { return !!this.form.weekdays?.includes(day); }
  save(): void {
    this.busy = true; this.message = '';
    const payload = {...this.form};
    if (payload.schedule_type === 'once' && payload.scheduled_at) {
      payload.scheduled_at = new Date(payload.scheduled_at).toISOString();
    }
    const request = this.editingId ? this.service.update(this.editingId, payload) : this.service.create(payload);
    request.subscribe({next: () => { this.busy = false; this.reset(); this.load(); },
      error: e => { this.busy = false; this.message = e?.error?.message ?? 'Could not save alarm'; }});
  }
  toggle(alarm: Alarm): void {
    this.service.action(alarm.id, alarm.enabled ? 'disable' : 'enable').subscribe(() => this.load());
  }
  test(alarm: Alarm): void {
    this.message = 'Call queued…';
    this.service.action(alarm.id, 'test').subscribe({next: () => this.message = 'Test call queued.',
      error: e => this.message = e?.error?.message ?? 'Could not queue call'});
  }
  snooze(alarm: Alarm): void { this.service.action(alarm.id, 'snooze', {minutes: 10}).subscribe(() => this.message = 'Snoozed 10 minutes.'); }
  remove(alarm: Alarm): void { if (confirm(`Delete alarm “${alarm.label}”?`)) this.service.delete(alarm.id).subscribe(() => { this.reset(); this.load(); }); }
  loadHistory(id: number): void { this.service.occurrences(id).subscribe(rows => this.occurrences = rows); }
  canCancel(item: AlarmOccurrence): boolean { return ['pending', 'calling', 'retrying'].includes(item.status); }
  cancel(item: AlarmOccurrence): void {
    if (!this.editingId) return;
    this.service.cancelOccurrence(this.editingId, item.id).subscribe({
      next: () => { this.message = 'Alarm occurrence cancelled.'; this.loadHistory(this.editingId!); },
      error: e => this.message = e?.error?.message ?? 'Could not cancel alarm',
    });
  }
  schedule(alarm: Alarm): string {
    if (alarm.schedule_type === 'once') return new Date(alarm.scheduled_at!).toLocaleString();
    const days = alarm.schedule_type === 'daily' ? 'Daily' : (alarm.weekdays ?? []).map(d => this.days[d]).join(', ');
    return `${days} ${alarm.local_time}`;
  }
  private localDateTime(date: Date): string {
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 16);
  }
}
