import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { CatchableMessage, MessageHandler, SnackbarMessage } from '../models/catchable-message';



@Injectable({ providedIn: 'root' })
export class MessageRegistryService {
  private handlers: Map<string, MessageHandler[]> = new Map();

  constructor(private snackBar: MatSnackBar) {
    this.setupBuiltInHandlers();
  }

  /**
   * Register a handler for a specific message type
   */
  register(messageType: string, handler: MessageHandler): void {
    if (!this.handlers.has(messageType)) {
      this.handlers.set(messageType, []);
    }
    this.handlers.get(messageType)!.push(handler);
  }

  /**
   * Catch a message and execute all registered handlers for that message type
   */
  async catch(message: CatchableMessage): Promise<void> {
    const handlers = this.handlers.get(message.type) || [];
    for (const handler of handlers) {
      await Promise.resolve(handler(message));
    }
  }

  /**
   * Unregister all handlers for a message type
   */
  unregister(messageType: string): void {
    this.handlers.delete(messageType);
  }

  /**
   * Get all registered message types
   */
  getRegisteredTypes(): string[] {
    return Array.from(this.handlers.keys());
  }

  /**
   * Setup built-in handlers
   */
  private setupBuiltInHandlers(): void {
    this.register('snackbar', (message: CatchableMessage) => {
      const snackMsg = message as SnackbarMessage;
      const { message: text, actions = [], duration = 5000, panelClass = [] } = snackMsg.payload;

      // If there are multiple actions, show the first one as the snackbar action, then add listeners
      if (actions.length > 0) {
        const firstAction = actions[0];
        const snackBarRef = this.snackBar.open(text, firstAction.label, {
          duration,
          panelClass,
          horizontalPosition: 'right',
          verticalPosition: 'top',
        });

        snackBarRef.onAction().subscribe(async () => {
          if (firstAction.callback) {
            await Promise.resolve(firstAction.callback());
          }
        });
      } else {
        // No actions, just show the message with a close button
        this.snackBar.open(text, 'OK', {
          duration,
          panelClass,
          horizontalPosition: 'right',
          verticalPosition: 'top',
        });
      }
    });
  }
}
