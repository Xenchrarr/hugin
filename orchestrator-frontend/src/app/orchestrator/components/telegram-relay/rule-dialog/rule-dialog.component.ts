import {Component, Inject} from '@angular/core';
import {
    MAT_DIALOG_DATA,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogRef,
    MatDialogTitle
} from '@angular/material/dialog';
import {MatButton} from '@angular/material/button';
import {MatCard, MatCardContent} from '@angular/material/card';
import {MatCheckbox} from '@angular/material/checkbox';
import {MatFormField, MatHint, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {FormsModule} from '@angular/forms';
import {NgIf} from '@angular/common';
import {TelegramRelayRule} from '../../../models/telegram-relay.model';
import {TelegramRelayService} from '../../../services/telegram-relay.service';

@Component({
    selector: 'app-rule-dialog',
    standalone: true,
    imports: [
        MatButton,
        MatDialogActions,
        MatDialogClose,
        MatDialogContent,
        MatDialogTitle,
        MatCard,
        MatCardContent,
        MatCheckbox,
        MatFormField,
        MatInput,
        MatLabel,
        MatHint,
        FormsModule,
        NgIf,
    ],
    templateUrl: './rule-dialog.component.html',
    styleUrl: './rule-dialog.component.css',
})
export class RuleDialogComponent {
    rule: TelegramRelayRule;
    isNew = false;
    conditionsJson = '';
    actionsJson = '';
    jsonError: string | null = null;

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: TelegramRelayRule | null,
        private relayService: TelegramRelayService,
        private dialogRef: MatDialogRef<RuleDialogComponent>,
    ) {
        if (!data) {
            this.rule = {
                id: 0, name: '', priority: 100, enabled: true,
                continue_on_match: false, is_preset: false, conditions: null, actions: []
            };
            this.isNew = true;
        } else {
            this.rule = {...data};
        }
        this.conditionsJson = this.rule.conditions ? JSON.stringify(this.rule.conditions, null, 2) : '';
        this.actionsJson = JSON.stringify(this.rule.actions, null, 2);
    }

    save() {
        this.jsonError = null;
        try {
            this.rule.conditions = this.conditionsJson.trim() ? JSON.parse(this.conditionsJson) : null;
            this.rule.actions = JSON.parse(this.actionsJson);
        } catch (e: any) {
            this.jsonError = 'Invalid JSON: ' + e.message;
            return;
        }
        this.relayService.saveRule(this.rule).subscribe(result => {
            this.dialogRef.close(result);
        });
    }
}
