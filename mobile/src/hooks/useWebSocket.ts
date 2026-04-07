import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { websocket } from '../services/WebSocketService';
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
  const failCountRef = useRef(0);

  useEffect(() => {
    // Connect (idempotent — singleton won't create duplicate connections)
    websocket.connect();

    // Connection handlers — returns cleanup functions
    const cleanupConnect = websocket.onConnect(() => {
      failCountRef.current = 0;
      setIsConnected(true);
      logger.info('WebSocket connected');
    });

    const cleanupDisconnect = websocket.onDisconnect(() => {
      failCountRef.current += 1;
      // Only show as disconnected after 3 failed attempts
      // This prevents the "Reconnecting" banner from flashing on startup
      if (failCountRef.current >= 3) {
        setIsConnected(false);
      }
      logger.info(`WebSocket disconnected (attempt ${failCountRef.current})`);
    });

    const cleanupError = websocket.onError((error) => {
      logger.warn('WebSocket error (silent):', error);
      // Never show toast — WebSocket is non-critical
    });

    // Set initial state
    setIsConnected(websocket.isConnected());

    // Cleanup on unmount — remove handlers, don't disconnect
    // (singleton stays alive for other consumers)
    return () => {
      cleanupConnect();
      cleanupDisconnect();
      cleanupError();
    };
  }, []);

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
  const { isConnected, subscribe } = useWebSocket();

  // Stabilize the assets array — only change when the actual values change
  const assetsKey = assets.sort().join(',');
  const stableAssets = useMemo(() => assets, [assetsKey]);

  useEffect(() => {
    if (!isConnected || stableAssets.length === 0) return;

    // Subscribe to price updates
    const unsubscribe = subscribe('price_update', (data: PriceUpdate) => {
      setPrices((prev) => {
        const newPrices = new Map(prev);
        newPrices.set(data.asset, data);
        return newPrices;
      });
    });

    // Request price updates (tracked for re-subscribe on reconnect)
    websocket.subscribeChannel('subscribe_prices', stableAssets);

    // Cleanup
    return () => {
      unsubscribe();
      websocket.unsubscribeChannel('unsubscribe_prices', stableAssets);
    };
  }, [isConnected, stableAssets, subscribe]);

  return {
    prices,
    isConnected,
  };
}
