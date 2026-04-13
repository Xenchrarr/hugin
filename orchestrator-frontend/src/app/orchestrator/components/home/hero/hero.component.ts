import { Component } from '@angular/core';
import {NgOptimizedImage} from "@angular/common";

@Component({
    selector: 'app-hero',
    templateUrl: './hero.component.html',
    styleUrls: ['./hero.component.css'],
    imports: [
        NgOptimizedImage
    ],
    standalone: true
})
export class HeroComponent {
}
