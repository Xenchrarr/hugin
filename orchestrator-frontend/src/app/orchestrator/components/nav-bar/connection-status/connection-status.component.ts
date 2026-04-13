import {Component, OnInit, OnDestroy} from '@angular/core';
import {NgClass, NgForOf} from "@angular/common";
import {ConnectionStatusService} from "../../../services/connection-status.service";
import {firstValueFrom} from "rxjs";

@Component({
    selector: 'app-connection-status',
    standalone: true,
    imports: [
        NgClass,
        NgForOf
    ],
    templateUrl: './connection-status.component.html',
    styleUrl: './connection-status.component.css'
})
export class ConnectionStatusComponent implements OnInit, OnDestroy {
    databases: any[] = [{name: 'backend', status: 'Disconnected'}];

    statusItems: any[] = ['backend'];
    private connectionStatusService: ConnectionStatusService;
    private intervalId: ReturnType<typeof setInterval> | null = null;

    backendUp: boolean = false;

    constructor(connectionStatusService: ConnectionStatusService) {
        this.connectionStatusService = connectionStatusService
    }

    ngOnInit(): void {

        this.getStatusItems();

        this.intervalId = setInterval(() => {
            this.getStatusForAllServices();
        }, 60000);

    }

    ngOnDestroy(): void {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }
    }

    randomStatus(): string {
        return Math.random() > 0.5 ? 'Connected' : 'Disconnected';
    }

    getStatusItems() {
        this.connectionStatusService.getStatusItems().subscribe((data) => {
            for (let item of data) {
                this.statusItems.push(item);
                this.mapStatus(item);
            }

            this.getStatusForAllServices();

        })
    }

    mapStatus(status: string) {
        let item = {name: status, status: 'Disconnected'};
        this.databases.push(item);
    }


    getStatusText(status: boolean): string {
        return status ? 'Connected' : 'Disconnected';
    }

    async getStatusForAllServices() {
        await this.checkBackendStatus();

        if (this.backendUp) {
            const statusPromises = this.databases
                .filter(db => db.name !== 'backend')
                .map(db => this.getStatus(db.name));

            await Promise.all(statusPromises);
        }
    }

    async checkBackendStatus() {
        try {
            const status = await firstValueFrom(this.connectionStatusService.checkIfBackendIsUp());
            this.backendUp = status;

            // Update the status of the backend database
            this.databases.forEach(db => {
                if (db.name === 'backend') {
                    db.status = this.getStatusText(status);
                }
            });

            if (this.databases.length === 1) {
                this.getStatusItems();
            }

            if (!this.backendUp) {
                this.databases.forEach(db => {
                    db.status = this.getStatusText(false);
                });
            }
        } catch (error) {
            console.error('Error checking backend status:', error);
        }
    }

    async getStatus(statusItem: string) {
        try {
            const data = await firstValueFrom(this.connectionStatusService.getStatus(statusItem));
            const status = data.status;

            // Update item with the new status
            this.databases.forEach(db => {
                if (db.name === statusItem) {
                    db.status = this.getStatusText(status);
                }
            });
        } catch (error) {
            console.error(`Error fetching status for ${statusItem}:`, error);
        }
    }

}
