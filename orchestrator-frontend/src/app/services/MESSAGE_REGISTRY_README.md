# Message Registry System

A lightweight, easy-to-use message catching and registry system for Angular applications.

## Overview

The Message Registry Service provides an elegant way to:
- **Register** handlers for specific message types
- **Catch** (dispatch) messages to all registered handlers
- **Use** built-in handlers like snackbar notifications with buttons
- **Extend** the system with custom message types and handlers

## Architecture

### Files

- **[message-registry.service.ts](./message-registry.service.ts)** - Core service that manages the registry
- **[catchable-message.ts](../models/catchable-message.ts)** - Message interfaces and types
- **[message-registry.example.ts](./message-registry.example.ts)** - Code examples
- **[message-registry-demo.component.ts](../components/message-registry-demo.component.ts)** - Demo component

## Quick Start

### Show a Snackbar with Button

```typescript
import { MessageRegistryService } from '@services/message-registry.service';
import { SnackbarMessage } from '@models/catchable-message';

constructor(private messageRegistry: MessageRegistryService) {}

showUndoSnackbar() {
  const msg: SnackbarMessage = {
    id: 'delete-undo-001',
    type: 'snackbar',
    payload: {
      message: 'Item deleted',
      actions: [
        {
          label: 'Undo',
          callback: async () => {
            await this.api.restoreItem();
          },
        },
      ],
      panelClass: ['snack-success'],
    },
  };

  this.messageRegistry.catch(msg);
}
```

### Register Custom Message Handler

```typescript
// Register a handler for a custom message type
this.messageRegistry.register('user-deleted', (message) => {
  console.log('User was deleted:', message.payload.userId);
  // Could trigger analytics, logging, etc.
});

// Multiple handlers can be registered for the same type
this.messageRegistry.register('user-deleted', (message) => {
  // This handler will also be called
  this.refreshUserList();
});

// Dispatch the message
this.messageRegistry.catch({
  id: 'user-delete-123',
  type: 'user-deleted',
  payload: {
    userId: '456',
    username: 'john_doe',
  },
});
```

## API Reference

### MessageRegistryService

#### `register(messageType: string, handler: MessageHandler): void`

Register a handler for a specific message type.

```typescript
this.messageRegistry.register('my-event', (msg) => {
  console.log('Message received:', msg);
});
```

#### `catch(message: CatchableMessage): Promise<void>`

Dispatch a message to all registered handlers.

```typescript
await this.messageRegistry.catch({
  id: 'msg-123',
  type: 'my-event',
  payload: { /* your data */ },
});
```

#### `unregister(messageType: string): void`

Remove all handlers for a message type.

```typescript
this.messageRegistry.unregister('my-event');
```

#### `getRegisteredTypes(): string[]`

Get list of all registered message types.

```typescript
const types = this.messageRegistry.getRegisteredTypes();
console.log('Registered message types:', types);
```

## Built-in Handlers

### Snackbar Handler

Displays notifications with optional action buttons.

**Message Type:** `'snackbar'`

**Payload Properties:**
- `message` (string) - The notification text
- `actions` (SnackbarAction[]) - Optional action buttons
- `duration` (number) - Duration in milliseconds (default: 5000)
- `panelClass` (string[]) - CSS classes to apply (e.g., `['snack-success']`, `['snack-error']`)

**SnackbarAction:**
- `label` (string) - Button text
- `callback` (function) - Optional function to execute when button is clicked
- `className` (string) - Optional CSS class for the button

**Examples:**

```typescript
// Simple message
this.messageRegistry.catch({
  id: 'msg-1',
  type: 'snackbar',
  payload: {
    message: 'Hello World!',
  },
});

// With button
this.messageRegistry.catch({
  id: 'msg-2',
  type: 'snackbar',
  payload: {
    message: 'Operation successful',
    actions: [{
      label: 'View Details',
      callback: () => this.router.navigate(['/details']),
    }],
    panelClass: ['snack-success'],
  },
});

// Error notification
this.messageRegistry.catch({
  id: 'msg-3',
  type: 'snackbar',
  payload: {
    message: 'Something went wrong',
    duration: 7000,
    panelClass: ['snack-error'],
  },
});
```

## Creating Custom Handlers

You can extend the system by creating custom handlers:

```typescript
// In your component or service
constructor(private messageRegistry: MessageRegistryService) {
  this.setupCustomHandlers();
}

private setupCustomHandlers() {
  // Analytics handler
  this.messageRegistry.register('page-view', (message) => {
    this.analytics.track('page_view', message.payload);
  });

  // Logger handler
  this.messageRegistry.register('error', (message) => {
    console.error('Caught error:', message.payload.error);
    // Send to error tracking service
    this.errorTracker.report(message.payload.error);
  });

  // Async handler
  this.messageRegistry.register('data-sync', async (message) => {
    await this.api.syncData(message.payload);
  });
}

// Dispatch custom messages
dispatchAnalytics() {
  this.messageRegistry.catch({
    id: 'pv-' + Date.now(),
    type: 'page-view',
    payload: {
      page: '/dashboard',
      time: new Date(),
    },
  });
}
```

## Best Practices

1. **Use meaningful message IDs** - Include context that identifies the message instance
2. **Document custom message types** - Add comments describing what each custom type does
3. **Handle async operations** - Use async/await in handlers if needed
4. **Keep handlers lightweight** - Offload heavy processing to services
5. **Register handlers early** - Often best done in component `ngOnInit()` or service constructor
6. **Unregister when needed** - Clean up handlers in `ngOnDestroy()` for components

## Example Component

See `message-registry-demo.component.ts` for a working example with buttons to test the system.

## Type Definitions

### CatchableMessage

```typescript
interface CatchableMessage {
  id: string;                    // Unique message identifier
  type: string;                  // Message type (targets registered handlers)
  payload: any;                  // Any data you want to pass
  timestamp?: number;            // Optional timestamp
}
```

### SnackbarMessage

```typescript
interface SnackbarMessage extends CatchableMessage {
  type: 'snackbar';
  payload: {
    message: string;
    actions?: SnackbarAction[];
    duration?: number;
    panelClass?: string[];
  };
}
```

### SnackbarAction

```typescript
interface SnackbarAction {
  label: string;
  callback?: () => void | Promise<void>;
  className?: string;
}
```

## Notes

- The service is provided at root level (singleton)
- Handlers are called in registration order
- Multiple handlers can be registered for the same message type
- Both sync and async handlers are supported
- The built-in snackbar handler uses Angular Material's MatSnackBar
