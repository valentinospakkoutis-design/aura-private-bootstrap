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
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private reconnectAttempts = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private isIntentionallyClosed = false;
  private onConnectHandlers: Set<ConnectionHandler> = new Set();
  private onDisconnectHandlers: Set<ConnectionHandler> = new Set();
  private onErrorHandlers: Set<ErrorHandler> = new Set();
  private activeSubscriptions: Set<string> = new Set();

  constructor(config: WebSocketConfig) {
    this.config = {
      reconnectInterval: 5000,
      maxReconnectAttempts: 5,
      ...config,
    };
  }

  // Connect to WebSocket (idempotent — safe to call multiple times)
  connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      logger.debug('WebSocket already connected or connecting, skipping');
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
        // Re-send active subscriptions after reconnect
        this.resubscribeAll();
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

  // Subscribe to message type (deduplicates by handler reference)
  on(type: string, handler: MessageHandler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.messageHandlers.delete(type);
        }
      }
    };
  }

  // Track a channel subscription (for re-subscribing after reconnect)
  subscribeChannel(channel: string, assets: string[]) {
    const key = `${channel}:${assets.sort().join(',')}`;
    if (this.activeSubscriptions.has(key)) {
      logger.debug(`Already subscribed to ${channel}, skipping`);
      return false;
    }
    this.activeSubscriptions.add(key);
    this.send(channel, { assets });
    return true;
  }

  unsubscribeChannel(channel: string, assets: string[]) {
    const key = `${channel}:${assets.sort().join(',')}`;
    this.activeSubscriptions.delete(key);
    this.send(channel, { assets });
  }

  // Re-send all tracked subscriptions after reconnect
  private resubscribeAll() {
    this.activeSubscriptions.forEach((key) => {
      const [channel, assetsStr] = key.split(':');
      const assets = assetsStr ? assetsStr.split(',') : [];
      if (assets.length > 0) {
        this.send(channel, { assets });
        logger.debug(`Re-subscribed to ${channel} after reconnect`);
      }
    });
  }

  // Connection event handlers (returns cleanup function)
  onConnect(handler: ConnectionHandler) {
    this.onConnectHandlers.add(handler);
    return () => { this.onConnectHandlers.delete(handler); };
  }

  onDisconnect(handler: ConnectionHandler) {
    this.onDisconnectHandlers.add(handler);
    return () => { this.onDisconnectHandlers.delete(handler); };
  }

  onError(handler: ErrorHandler) {
    this.onErrorHandlers.add(handler);
    return () => { this.onErrorHandlers.delete(handler); };
  }

  // Get connection status
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // Private methods
  private scheduleReconnect() {
    this.clearReconnectTimeout();
    this.reconnectAttempts++;

    const delay = Math.max(3000, this.config.reconnectInterval! * this.reconnectAttempts);
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
  // Always use the configured API base URL (works in both dev and production)
  try {
    const { getApiBaseUrl } = require('../config/environment');
    const apiUrl = getApiBaseUrl();
    if (apiUrl) {
      // Convert https:// → wss://, http:// → ws://
      const wsUrl = apiUrl.replace(/^https:\/\//, 'wss://').replace(/^http:\/\//, 'ws://');
      return wsUrl + '/ws';
    }
  } catch (error) {
    console.warn('Failed to get API URL for WebSocket:', error);
  }

  return 'wss://aura-private-bootstrap-production.up.railway.app/ws';
};

export const websocket = new WebSocketService({
  url: getWebSocketUrl(),
  reconnectInterval: 5000,
  maxReconnectAttempts: 5,
});
