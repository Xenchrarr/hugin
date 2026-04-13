export class GitRepo {
    id: number = 0;
    name: string = '';
    url: string = '';
    branch: string = 'main';
    enabled: boolean = true;
    created: string | undefined = undefined;
    updated: string | undefined = undefined;

    constructor(init?: Partial<GitRepo>) {
        Object.assign(this, init);
    }
}
