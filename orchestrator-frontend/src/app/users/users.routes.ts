import { Routes } from '@angular/router';
import { adminGuard } from '../auth/admin.guard';
import { UserListComponent } from './components/admin/user-list/user-list.component';
import { NotificationSettingsComponent } from './components/admin/notification-settings/notification-settings.component';

export const routes: Routes = [
  { path: '', redirectTo: 'list', pathMatch: 'full' },
  { path: 'list', component: UserListComponent, canActivate: [adminGuard] },
  { path: 'notification-settings', component: NotificationSettingsComponent, canActivate: [adminGuard] },
];
