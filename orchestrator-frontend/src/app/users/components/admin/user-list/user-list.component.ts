import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { NgIf, NgFor } from '@angular/common';
import { CreateUserPayload, UpdateUserPayload, User, UserConfig } from '../../../user.model';
import { UserService } from '../../../user.service';

@Component({
  selector: 'app-user-list',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule, MatCardModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatTableModule,
    MatIconModule, MatChipsModule, MatSlideToggleModule,
    NgIf, NgFor,
  ],
  templateUrl: './user-list.component.html',
  styleUrl: './user-list.component.scss',
})
export class UserListComponent implements OnInit {
  users = signal<User[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);

  editing = signal<User | null>(null);
  creating = signal(false);

  form: CreateUserPayload & UpdateUserPayload = this._blank();

  editingPermissionsUserId = signal<number | null>(null);
  editingPermissions = signal<string[]>([]);
  selectedCommandPaths: string[] = [];

  readonly columns = ['username', 'display_name', 'phone_number', 'telegram_user_id', 'is_admin', 'actions'];
  readonly channelOptions = ['sms', 'telegram', 'teams'];
  readonly inverterTypes: Array<'growatt' | 'ecoflow' | null> = [null, 'growatt', 'ecoflow'];

  private readonly _smsCommands = [
    'help', 'list/show', 'list/add', 'list/rm',
    'rem/in', 'rem/list', 'rem/snooze', 'rem/dismiss',
    'home/dev', 'chart',
  ];
  knownCommands = signal<string[]>(this._smsCommands);

  constructor(private svc: UserService) {}

  ngOnInit(): void {
    this.load();
    this.svc.getBotCommands().subscribe({
      next: registry => {
        const botCommands = Object.values(registry).flat();
        const merged = [...new Set([...this._smsCommands, ...botCommands])].sort();
        this.knownCommands.set(merged);
      },
    });
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
      is_admin: user.is_admin,
      config: { ...user.config },
    };
  }

  cancel(): void {
    this.editing.set(null);
    this.creating.set(false);
    this.error.set(null);
    this.editingPermissionsUserId.set(null);
    this.editingPermissions.set([]);
    this.selectedCommandPaths = [];
  }

  save(): void {
    if (this.creating()) {
      const payload: CreateUserPayload = {
        username: this.form.username!,
        password: this.form.password!,
        display_name: this.form.display_name || undefined,
        phone_number: this.form.phone_number || undefined,
        telegram_user_id: this.form.telegram_user_id || undefined,
        is_admin: this.form.is_admin ?? false,
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
        is_admin: this.form.is_admin ?? false,
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
    return { username: '', password: '', display_name: '', phone_number: '', telegram_user_id: null, is_admin: false, config: {} };
  }

  openPermissions(user: User): void {
    this.editingPermissionsUserId.set(user.id);
    this.editingPermissions.set([]);
    this.selectedCommandPaths = [];
    this.error.set(null);
    this.svc.getCommandPermissions(user.id).subscribe({
      next: r => this.editingPermissions.set(r.allowed_commands),
      error: e => this.error.set(e?.error?.message ?? 'Failed to load permissions'),
    });
  }

  closePermissions(): void {
    this.editingPermissionsUserId.set(null);
    this.editingPermissions.set([]);
    this.selectedCommandPaths = [];
  }

  addPermission(): void {
    const toAdd = this.selectedCommandPaths.filter(p => !this.editingPermissions().includes(p));
    if (!toAdd.length) return;
    const userId = this.editingPermissionsUserId()!;
    forkJoin(toAdd.map(path => this.svc.addCommandPermission(userId, path))).subscribe({
      next: () => {
        this.editingPermissions.update(p => [...p, ...toAdd].sort());
        this.selectedCommandPaths = [];
      },
      error: e => this.error.set(e?.error?.message ?? 'Failed to add permission'),
    });
  }

  removePermission(commandPath: string): void {
    const userId = this.editingPermissionsUserId()!;
    this.svc.removeCommandPermission(userId, commandPath).subscribe({
      next: () => this.editingPermissions.update(p => p.filter(x => x !== commandPath)),
      error: e => this.error.set(e?.error?.message ?? 'Failed to remove permission'),
    });
  }
}
