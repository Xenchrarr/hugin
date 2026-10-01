import {CommonModule, JsonPipe} from '@angular/common';
import {Component, OnDestroy, OnInit} from '@angular/core';
import {MatCardModule} from '@angular/material/card';
import {MatButtonModule} from '@angular/material/button';
import {MatIconModule} from '@angular/material/icon';
import {ActivatedRoute, RouterLink} from '@angular/router';
import {Subscription, timer, switchMap} from 'rxjs';
import {WorkflowRunDetail} from '../../models/workflow';
import {WorkflowService} from '../../services/workflow.service';
import {JobLogsService} from '../../services/job-logs.service';
import {JobRunService} from '../../services/job-run.service';
import {JobLog} from '../../models/job-log';

@Component({
 selector:'app-execution-detail', standalone:true,
 imports:[CommonModule,JsonPipe,MatButtonModule,MatCardModule,MatIconModule,RouterLink],
 templateUrl: './execution-detail.component.html',
 styleUrl: './execution-detail.component.scss',
})
export class ExecutionDetailComponent implements OnInit,OnDestroy{
 detail:WorkflowRunDetail|null=null;logs:Record<string,JobLog[]>={};private subscription?:Subscription;
 constructor(private route:ActivatedRoute,private api:WorkflowService,private logApi:JobLogsService,private runApi:JobRunService){}
 ngOnInit(){const id=this.route.snapshot.paramMap.get('runId')!;this.subscription=timer(0,3000).pipe(switchMap(()=>this.api.run(id))).subscribe(d=>{this.detail=d;if(d.run.status!=='Started')this.subscription?.unsubscribe();});}
 ngOnDestroy(){this.subscription?.unsubscribe();} icon(s:string){return s==='Finished'?'check_circle':s==='Error'?'error':s==='Started'?'pending':'radio_button_checked';}
 hasKeys(value:Record<string,unknown>){return Object.keys(value||{}).length>0;}
 loadLogs(stepId:string){if(!this.detail)return;this.logApi.getLogsForJob(this.detail.run.id as string,undefined,stepId).subscribe(value=>this.logs[stepId]=value);}
 cancel(){if(!this.detail)return;this.runApi.cancelJobRun(this.detail.run.id as string).subscribe();}
}
