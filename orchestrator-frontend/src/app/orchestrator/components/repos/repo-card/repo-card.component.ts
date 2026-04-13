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
import {MatFormField, MatLabel} from '@angular/material/form-field';
import {MatInput} from '@angular/material/input';
import {FormsModule} from '@angular/forms';
import {GitRepo} from '../../../models/git-repo';
import {GitRepoService} from '../../../services/git-repo.service';

@Component({
    selector: 'app-repo-card',
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
        FormsModule,
    ],
    templateUrl: './repo-card.component.html',
    styleUrl: './repo-card.component.css'
})
export class RepoCardComponent {
    repo: GitRepo;
    isNew = false;

    constructor(
        @Inject(MAT_DIALOG_DATA) public data: GitRepo,
        private repoService: GitRepoService,
        private dialogRef: MatDialogRef<RepoCardComponent>
    ) {
        if (!data) {
            this.repo = new GitRepo();
            this.isNew = true;
        } else {
            this.repo = new GitRepo(data);
        }
    }

    saveRepo() {
        this.repoService.saveRepo(this.repo).subscribe(repo => {
            this.dialogRef.close(repo);
        });
    }
}
