import {Routes} from '@angular/router';
import {HomeComponent} from "./components/home/home.component";
import {ErrorComponent} from "./components/error/error.component";
import {JobsComponent} from "./components/jobs/jobs.component";
import {ReposComponent} from "./components/repos/repos.component";
import {ScriptsPageComponent} from "./components/scripts-page/scripts-page.component";
import {RunsPageComponent} from "./components/runs-page/runs-page.component";
import {RemindersComponent} from "./components/reminders/reminders.component";
import {TelegramRelayComponent} from './components/telegram-relay/telegram-relay.component';
import {CalendarComponent} from './components/calendar/calendar.component';
import {MessageHubComponent} from './components/message-hub/message-hub.component';
import {adminGuard} from '../auth/admin.guard';
import {AlarmsComponent} from './components/alarms/alarms.component';
import {ReticulumChatComponent} from './components/reticulum-chat/reticulum-chat.component';

export const routes: Routes = [
    {
        path: '',
        redirectTo: 'scripts',
        pathMatch: 'full',
    },
    {
        path: 'scripts',
        component: ScriptsPageComponent,
    },
    {
        path: 'runs',
        component: RunsPageComponent,
    },
    {
        path: 'home',
        component: HomeComponent,
    },
    {
        path: 'error',
        component: ErrorComponent,
    },
    {
        path: 'jobs',
        component: JobsComponent,
    },
    {
        path: 'repos',
        component: ReposComponent,
    },
    {
        path: 'reminders',
        component: RemindersComponent,
    },
    {
        path: 'alarms',
        component: AlarmsComponent,
    },
    {
        path: 'reticulum-chat',
        component: ReticulumChatComponent,
    },
    {
        path: 'telegram-relay',
        component: TelegramRelayComponent,
    },
    {
        path: 'message-hub',
        component: MessageHubComponent,
        canActivate: [adminGuard],
    },
    {
        path: 'calendar',
        component: CalendarComponent,
    },
];
