import {Component} from '@angular/core';
import {MatToolbar} from '@angular/material/toolbar';
import {NgIf} from '@angular/common';
import {environment} from '../../../environments/environment';

@Component({
  selector: 'app-nav-bar-component',
    imports: [
        MatToolbar,
        NgIf,
    ],
  templateUrl: './nav-bar.component.html',
  styleUrl: './nav-bar.component.scss',
})
export class NavBarComponent {
    isProd = environment.production;
}
