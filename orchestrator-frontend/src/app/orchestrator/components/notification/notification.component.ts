import {Component, Inject, inject, Input} from '@angular/core';
import {
    MAT_SNACK_BAR_DATA,
    MatSnackBar,
    MatSnackBarAction,
    MatSnackBarActions,
    MatSnackBarLabel,
    MatSnackBarRef
} from "@angular/material/snack-bar";
import {MatButton} from "@angular/material/button";

@Component({
    selector: 'app-notification',
    standalone: true,
    imports: [
        MatSnackBarAction,
        MatButton,
        MatSnackBarActions,
        MatSnackBarLabel
    ],
    templateUrl: './notification.component.html',
    styleUrl: './notification.component.css'
})
export class NotificationComponent {
    @Input()
    message: string = '';
    type = 'default';

    snackBarRef = inject(MatSnackBarRef);

    constructor(@Inject(MAT_SNACK_BAR_DATA) public data: any) {
        this.message = data.message;
        this.type = data.type;
    }

}
