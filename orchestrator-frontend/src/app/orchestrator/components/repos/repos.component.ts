import {Component, inject, OnInit} from '@angular/core';
import {GitRepo} from '../../models/git-repo';
import {GitRepoService} from '../../services/git-repo.service';
import {MatButton} from '@angular/material/button';
import {
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell,
    MatHeaderCellDef,
    MatHeaderRow,
    MatHeaderRowDef,
    MatRow,
    MatRowDef,
    MatTable
} from '@angular/material/table';

import {MatCheckbox} from '@angular/material/checkbox';
import {NgIf} from '@angular/common';
import {MatDialog} from '@angular/material/dialog';
import {RepoCardComponent} from './repo-card/repo-card.component';
import {ConfirmDialogComponent} from '../confirm-dialog/confirm-dialog.component';

@Component({
    selector: 'app-repos',
    standalone: true,
    imports: [
        MatButton,
        MatCell,
        MatCellDef,
        MatColumnDef,
        MatHeaderCell,
        MatHeaderCellDef,
        MatHeaderRow,
        MatHeaderRowDef,
        MatRow,
        MatRowDef,
        MatTable,
        MatCheckbox,
        NgIf,
    ],
    templateUrl: './repos.component.html',
    styleUrl: './repos.component.css'
})
export class ReposComponent implements OnInit {
    repos: GitRepo[] = [];
    readonly dialog = inject(MatDialog);

    displayedColumns: string[] = ['id', 'name', 'url', 'branch', 'enabled', 'actions'];

    constructor(private repoService: GitRepoService) {
    }

    ngOnInit() {
        this.loadRepos();
    }

    loadRepos() {
        this.repoService.getRepos().subscribe(repos => {
            this.repos = repos;
        });
    }

    addRepo() {
        const dialogRef = this.dialog.open(RepoCardComponent, {
            data: undefined,
            width: '600px',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.loadRepos();
            }
        });
    }

    editRepo(repo: GitRepo) {
        const dialogRef = this.dialog.open(RepoCardComponent, {
            data: repo,
            width: '600px',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.loadRepos();
            }
        });
    }

    confirmDeleteRepo(repo: GitRepo): void {
        const dialogRef = this.dialog.open(ConfirmDialogComponent, {
            data: {title: 'Delete Repo?', message: `Are you sure you want to delete "${repo.name || repo.url}"?`, confirmLabel: 'Delete'},
            width: '400px',
        });
        dialogRef.afterClosed().subscribe(result => {
            if (result) {
                this.deleteRepo(repo);
            }
        });
    }

    deleteRepo(repo: GitRepo): void {
        this.repoService.deleteRepo(repo.id).subscribe({
            next: () => this.loadRepos(),
            error: () => this.loadRepos(),
        });
    }
}
