import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { NgIf, NgFor } from '@angular/common';
import { CreateUserPayload, UpdateUserPayload, User, UserConfig } from './user.model';
import { UserService } from './user.service';

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule, MatCardModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatTableModule,
    MatIconModule, MatChipsModule, NgIf, NgFor,
  ],
  templateUrl: './users.component.html',
  styleUrl: './users.component.scss',
})
export class UsersComponent implements OnInit {
  users = signal<User[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);

  editing = signal<User | null>(null);
  creating = signal(false);

  form: CreateUserPayload & UpdateUserPayload = this._blank();

  readonly columns = ['username', 'display_name', 'phone_number', 'telegram_user_id', 'actions'];
  readonly channelOptions = ['sms', 'telegram', 'teams'];
  readonly inverterTypes: Array<'growatt' | 'ecoflow' | null> = [null, 'growatt', 'ecoflow'];

  constructor(private svc: UserService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.svc.list().subscribe({
      next: users => { this.users.set(users); this.loading.set(false); },
      error: e => { this.error.set(e?.error?.message ?? 'Failed to load users'); this.loading.set(false); },
    });
  }

  startCreate(): void {
    this.form = this._blank();
    this.creating.set(true);
    this.editing.set(null);
  }

  startEdit(user: User): void {
    this.editing.set(user);
    this.creating.set(false);
    this.form = {
      username: user.username,
      password: '',
      display_name: user.display_name ?? '',
      phone_number: user.phone_number ?? '',
      telegram_user_id: user.telegram_user_id ?? null,
      config: { ...user.config },
    };
  }

  cancel(): void {
    this.editing.set(null);
    this.creating.set(false);
  }

  save(): void {
    if (this.creating()) {
      const payload: CreateUserPayload = {
        username: this.form.username!,
        password: this.form.password!,
        display_name: this.form.display_name || undefined,
        phone_number: this.form.phone_number || undefined,
        telegram_user_id: this.form.telegram_user_id || undefined,
        config: this.form.config,
      };
      this.svc.create(payload).subscribe({
        next: () => { this.cancel(); this.load(); },
        error: e => this.error.set(e?.error?.message ?? 'Failed to create user'),
      });
    } else if (this.editing()) {
      const id = this.editing()!.id;
      const payload: UpdateUserPayload = {
        display_name: this.form.display_name || undefined,
        phone_number: this.form.phone_number || null,
        telegram_user_id: this.form.telegram_user_id || null,
        config: this.form.config,
      };
      if (this.form.password) {
        payload.password = this.form.password;
      }
      this.svc.update(id, payload).subscribe({
        next: () => { this.cancel(); this.load(); },
        error: e => this.error.set(e?.error?.message ?? 'Failed to update user'),
      });
    }
  }

  delete(user: User): void {
    if (!confirm(`Delete user "${user.username}"?`)) return;
    this.svc.delete(user.id).subscribe({
      next: () => this.load(),
      error: e => this.error.set(e?.error?.message ?? 'Failed to delete user'),
    });
  }

  toggleChannel(channel: string): void {
    const channels = this.form.config?.default_channels ?? [];
    const idx = channels.indexOf(channel);
    if (idx >= 0) {
      channels.splice(idx, 1);
    } else {
      channels.push(channel);
    }
    this.form.config = { ...this.form.config, default_channels: channels };
  }

  hasChannel(channel: string): boolean {
    return (this.form.config?.default_channels ?? []).includes(channel);
  }

  private _blank(): CreateUserPayload & UpdateUserPayload {
    return { username: '', password: '', display_name: '', phone_number: '', telegram_user_id: null, config: {} };
  }
}
