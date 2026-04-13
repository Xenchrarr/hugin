import { Component } from '@angular/core';
import { HomeContentComponent } from './home-content/home-content.component';
import { HeroComponent } from './hero/hero.component';
import { LoadingComponent } from '../loading/loading.component';
import { AsyncPipe, NgIf } from '@angular/common';

@Component({
    selector: 'app-home',
    templateUrl: './home.component.html',
    styleUrls: ['./home.component.css'],
    standalone: true,
    imports: [
        HomeContentComponent,
        HeroComponent,
        LoadingComponent,
        AsyncPipe,
        NgIf
    ]
})
export class HomeComponent {
    constructor() {}
}
