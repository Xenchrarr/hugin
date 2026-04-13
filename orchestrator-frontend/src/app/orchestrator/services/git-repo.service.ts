import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {map} from 'rxjs/operators';
import {environment} from '../../../environments/environment';
import {GitRepo} from '../models/git-repo';

@Injectable({
    providedIn: 'root'
})
export class GitRepoService {
    private baseUrl: string;

    constructor(private http: HttpClient) {
        this.baseUrl = environment.apiOrchestratorUri + '/git_repos';
    }

    getRepos(): Observable<GitRepo[]> {
        return this.http.get<any[]>(this.baseUrl + '/list').pipe(
            map(data => data.map(item => new GitRepo(item)))
        );
    }

    getRepo(id: number): Observable<GitRepo> {
        return this.http.get<any>(this.baseUrl + '/get?repo_id=' + id).pipe(
            map(data => new GitRepo(data))
        );
    }

    saveRepo(repo: GitRepo): Observable<GitRepo> {
        return this.http.post<any>(this.baseUrl + '/', repo).pipe(
            map(data => new GitRepo(data))
        );
    }

    deleteRepo(id: number): Observable<any> {
        return this.http.delete(this.baseUrl + '/' + id);
    }
}
