import { AsyncPipe, NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, timer } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

@Component({
  selector: 'app-error',
  templateUrl: './error.component.html',
  styleUrl: './error.component.scss',
  standalone: true,
  imports: [
    AsyncPipe,
    NgIf
  ]
})
export class ErrorComponent implements OnInit {



  constructor( private router: Router) {

  }

  ngOnInit() {
    // timer(0).pipe(takeUntil(this.error$)).subscribe(() => {
    //   this.router.navigateByUrl('/');
    // });
  }
}

