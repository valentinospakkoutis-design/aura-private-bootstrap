import { logger } from '../utils/Logger';

type MessageHandler = (data: any) => void;
type ErrorHandler = (error: Event) => void;
type ConnectionHandler = () => void;

interface WebSocketConfig {
  url: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private reconnectAttempts = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private isIntentionallyClosed = false;
  private onConnectHandlers: ConnectionHandler[] = [];
  private onDisconnectHandlers: ConnectionHandler[] = [];
  private onErrorHandlers: ErrorHandler[] = [];

  constructor(config: WebSocketConfig) {
    this.config = {
      reconnectInterval: 5000,
      maxReconnectAttempts: 5,
      ...config,
    };
  }

  // Connect to WebSocket
  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      logger.warn('WebSocket already connected');
      return;
    }

    this.isIntentionallyClosed = false;
    logger.info('Connecting to WebSocket:', this.config.url);

    try {
      this.ws = new WebSocket(this.config.url);

      this.ws.onopen = () => {
        logger.info('WebSocket connected');
        this.reconnectAttempts = 0;
        this.onConnectHandlers.forEach((handler) => handler());
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          logger.debug('WebSocket message received:', data);

          const { type, payload } = data;
          const handlers = this.messageHandlers.get(type);

          if (handlers) {
            handlers.forEach((handler) => handler(payload));
          }
        } catch (error) {
          logger.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        logger.error('WebSocket error:', error);
        this.onErrorHandlers.forEach((handler) => handler(error));
      };

      this.ws.onclose = (event) => {
        logger.info('WebSocket disconnected:', event.code, event.reason);
        this.onDisconnectHandlers.forEach((handler) => handler());

        // Auto-reconnect if not intentionally closed
        if (!this.isIntentionallyClosed && this.reconnectAttempts < this.config.maxReconnectAttempts!) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      logger.error('Failed to create WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  // Disconnect from WebSocket
  disconnect() {
    this.isIntentionallyClosed = true;
    this.clearReconnectTimeout();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    logger.info('WebSocket disconnected intentionally');
  }

  // Send message
  send(type: string, payload: any) {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      logger.warn('WebSocket not connected, cannot send message');
      return false;
    }

    try {
      const message = JSON.stringify({ type, payload });
      this.ws.send(message);
      logger.debug('WebSocket message sent:', { type, payload });
      return true;
    } catch (error) {
      logger.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  // Subscribe to message type
  on(type: string, handler: MessageHandler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  // Connection event handlers
  onConnect(handler: ConnectionHandler) {
    this.onConnectHandlers.push(handler);
  }

  onDisconnect(handler: ConnectionHandler) {
    this.onDisconnectHandlers.push(handler);
  }

  onError(handler: ErrorHandler) {
    this.onErrorHandlers.push(handler);
  }

  // Get connection status
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // Private methods
  private scheduleReconnect() {
    this.clearReconnectTimeout();
    this.reconnectAttempts++;

    const delay = this.config.reconnectInterval! * this.reconnectAttempts;
    logger.info(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private clearReconnectTimeout() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }
}

// Create singleton instance
// Get WebSocket URL from environment config
const getWebSocketUrl = () => {
  if (__DEV__) {
    return 'ws://localhost:8000/ws';
  }
  
  // In production, use the API URL but with ws/wss protocol
  try {
    const { getApiBaseUrl } = require('../config/environment');
    const apiUrl = getApiBaseUrl();
    if (apiUrl) {
      // Convert http/https to ws/wss
      return apiUrl.replace(/^http/, 'ws').replace(/^https/, 'wss') + '/ws';
    }
  } catch (error) {
    console.warn('Failed to get API URL for WebSocket:', error);
  }
  
  return 'wss://api.aura.app/ws';
};

export const websocket = new WebSocketService({ 
  url: getWebSocketUrl(),
  reconnectInterval: 5000,
  maxReconnectAttempts: 5,
});

