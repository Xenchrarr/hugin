/**
 * Represents a message that can be caught and handled by registered handlers
 */
export interface CatchableMessage {
  id: string;
  type: string;
  payload: any;
  timestamp?: number;
}

/**
 * Handler function that processes a catchable message
 */
export type MessageHandler = (message: CatchableMessage) => void | Promise<void>;

/**
 * Configuration for a snackbar action button
 */
export interface SnackbarAction {
  label: string;
  callback?: () => void | Promise<void>;
  className?: string;
}

/**
 * Specific message for snackbar display with buttons
 */
export interface SnackbarMessage extends CatchableMessage {
  type: 'snackbar';
  payload: {
    message: string;
    actions?: SnackbarAction[];
    duration?: number;
    panelClass?: string[];
  };
}
