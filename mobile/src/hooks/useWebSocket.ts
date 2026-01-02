import { useEffect, useState, useCallback } from 'react';
import { websocket } from '../services/WebSocketService';
import { useAppStore } from '../stores/appStore';
import { logger } from '../utils/Logger';

interface PriceUpdate {
  asset: string;
  price: number;
  change: number;
  changePercentage: number;
  timestamp: string;
}

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const { showToast } = useAppStore();

  useEffect(() => {
    // Connect on mount
    websocket.connect();

    // Connection handlers
    websocket.onConnect(() => {
      setIsConnected(true);
      logger.info('WebSocket connected');
    });

    websocket.onDisconnect(() => {
      setIsConnected(false);
      logger.info('WebSocket disconnected');
    });

    websocket.onError((error) => {
      logger.error('WebSocket error:', error);
      showToast('Connection error', 'error');
    });

    // Cleanup on unmount
    return () => {
      websocket.disconnect();
    };
  }, [showToast]);

  const subscribe = useCallback((type: string, handler: (data: any) => void) => {
    return websocket.on(type, handler);
  }, []);

  const send = useCallback((type: string, payload: any) => {
    return websocket.send(type, payload);
  }, []);

  return {
    isConnected,
    subscribe,
    send,
  };
}

// Specialized hook for price updates
export function usePriceUpdates(assets: string[]) {
  const [prices, setPrices] = useState<Map<string, PriceUpdate>>(new Map());
  const { subscribe, send, isConnected } = useWebSocket();

  useEffect(() => {
    if (!isConnected || assets.length === 0) return;

    // Subscribe to price updates
    const unsubscribe = subscribe('price_update', (data: PriceUpdate) => {
      setPrices((prev) => {
        const newPrices = new Map(prev);
        newPrices.set(data.asset, data);
        return newPrices;
      });
    });

    // Request price updates for assets
    send('subscribe_prices', { assets });

    // Cleanup
    return () => {
      unsubscribe();
      send('unsubscribe_prices', { assets });
    };
  }, [isConnected, assets, subscribe, send]);

  return {
    prices,
    isConnected,
  };
}

