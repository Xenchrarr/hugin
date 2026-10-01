import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {environment} from '../../../environments/environment';

@Injectable({providedIn:'root'})
export class MonitorService{
 private base=environment.apiOrchestratorUri+'/monitors';
 constructor(private http:HttpClient){}
 list(){return this.http.get<any[]>(this.base+'/list');}
 get(key:string){return this.http.get<any>(`${this.base}/${encodeURIComponent(key)}`);}
 run(key:string){return this.http.post<any>(`${this.base}/${encodeURIComponent(key)}/run`,{});}
 enabled(key:string,value:boolean|null){return this.http.put(`${this.base}/${encodeURIComponent(key)}/enabled`,{enabled:value});}
 retryIncident(id:string){return this.http.post<{job_run_id:string}>(`${this.base}/incidents/${encodeURIComponent(id)}/retry`,{});}
}
