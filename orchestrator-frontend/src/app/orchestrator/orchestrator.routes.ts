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
        path: 'telegram-relay',
        component: TelegramRelayComponent,
    },
    {
        path: 'calendar',
        component: CalendarComponent,
    },
];
