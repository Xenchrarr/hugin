import {Component, inject} from '@angular/core';
import {MatToolbar} from '@angular/material/toolbar';
import {MatButton, MatIconButton} from '@angular/material/button';
import {MatIcon} from '@angular/material/icon';
import {NgIf} from '@angular/common';
import {RouterLink} from '@angular/router';
import {Router} from '@angular/router';
import {environment} from '../../../environments/environment';
import {AuthService} from '../../auth/auth.service';

@Component({
  selector: 'app-nav-bar-component',
    imports: [
        MatToolbar,
        MatButton,
        MatIconButton,
        MatIcon,
        NgIf,
        RouterLink,
    ],
  templateUrl: './nav-bar.component.html',
  styleUrl: './nav-bar.component.scss',
})
export class NavBarComponent {
    isProd = environment.production;

    private auth = inject(AuthService);
    private router = inject(Router);

    get isLoggedIn(): boolean {
        return this.auth.isLoggedIn();
    }

    get username(): string | null {
        return this.auth.currentUser?.username ?? null;
    }

    logout(): void {
        this.auth.logout();
        this.router.navigateByUrl('/login');
    }
}
