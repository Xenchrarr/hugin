import {Component, Inject} from '@angular/core';
import {
    MAT_DIALOG_DATA,
    MatDialogActions,
    MatDialogContent,
    MatDialogRef,
    MatDialogTitle,
} from '@angular/material/dialog';
import {MatButton} from '@angular/material/button';
import {MatFormField, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {MatCheckbox} from '@angular/material/checkbox';
import {FormsModule} from '@angular/forms';
import {IcalSource} from '../../../models/ical-source';
import {IcalService} from '../../../services/ical.service';

@Component({
    selector: 'app-source-dialog',
    standalone: true,
    imports: [
        FormsModule,
        MatButton,
        MatDialogActions,
        MatDialogContent,
        MatDialogTitle,
        MatFormField,
        MatInput,
        MatLabel,
        MatCheckbox,
    ],
    templateUrl: './source-dialog.component.html',
    styleUrl: './source-dialog.component.scss',
})
export class SourceDialogComponent {
    source: IcalSource;
    isNew: boolean;

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: IcalSource | undefined,
        private icalService: IcalService,
        private dialogRef: MatDialogRef<SourceDialogComponent>,
    ) {
        if (!data) {
            this.source = new IcalSource();
            this.isNew = true;
        } else {
            this.source = new IcalSource(data);
            this.isNew = false;
        }
    }

    save() {
        const payload: Partial<IcalSource> = {
            name: this.source.name,
            url: this.source.url,
            enabled: this.source.enabled,
            color: this.source.color,
        };

        const op = this.isNew
            ? this.icalService.createSource(payload)
            : this.icalService.updateSource(this.source.id, payload);

        op.subscribe({
            next: result => this.dialogRef.close(result),
            error: () => {},
        });
    }
}
