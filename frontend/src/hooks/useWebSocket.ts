'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useSession } from 'next-auth/react';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001';
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebSocketMessage<T = unknown> {
  type: string;
  data?: T;
  ticker?: string;
  error?: string;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(
  endpoint: string,
  options: UseWebSocketOptions = {}
) {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const { data: session } = useSession();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const connect = useCallback(() => {
    // Mock mode - pretend we're connected without actual WebSocket
    if (MOCK_MODE) {
      setStatus('connected');
      onConnect?.();
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    // Build WebSocket URL with optional auth token
    let url = `${WS_URL}${endpoint}`;
    if (session?.accessToken && endpoint.includes('watchlist')) {
      url += `?token=${session.accessToken}`;
    }

    setStatus('connecting');

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setStatus('connected');
        reconnectAttemptsRef.current = 0;
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          setLastMessage(message);
          onMessage?.(message);
        } catch {
          console.error('Failed to parse WebSocket message:', event.data);
        }
      };

      ws.onclose = () => {
        setStatus('disconnected');
        onDisconnect?.();

        // Attempt reconnection
        if (
          autoReconnect &&
          reconnectAttemptsRef.current < maxReconnectAttempts
        ) {
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        setStatus('error');
        onError?.(error);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setStatus('error');
    }
  }, [
    endpoint,
    session?.accessToken,
    autoReconnect,
    reconnectInterval,
    maxReconnectAttempts,
    onConnect,
    onDisconnect,
    onMessage,
    onError,
  ]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const subscribe = useCallback(
    (ticker: string) => {
      send({ action: 'subscribe', ticker });
    },
    [send]
  );

  const unsubscribe = useCallback(
    (ticker: string) => {
      send({ action: 'unsubscribe', ticker });
    },
    [send]
  );

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    status,
    lastMessage,
    send,
    subscribe,
    unsubscribe,
    connect,
    disconnect,
  };
}
