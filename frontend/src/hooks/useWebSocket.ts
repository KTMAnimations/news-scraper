'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useSession } from 'next-auth/react';

// WebSocket URL - connects to the backend WebSocket server on port 8765
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8765';
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'error';

export interface WebSocketMessage<T = unknown> {
  type: string;
  data?: T;
  ticker?: string;
  error?: string;
  timestamp?: string;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onBatchedMessages?: (messages: WebSocketMessage[]) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
  // Exponential backoff settings
  initialReconnectDelay?: number;
  maxReconnectDelay?: number;
  reconnectBackoffMultiplier?: number;
  // Event batching settings
  enableBatching?: boolean;
  batchInterval?: number;
  maxBatchSize?: number;
}

// Calculate exponential backoff delay
function calculateBackoffDelay(
  attempt: number,
  initialDelay: number,
  maxDelay: number,
  multiplier: number
): number {
  // Add jitter to prevent thundering herd
  const jitter = Math.random() * 0.3 + 0.85; // 0.85 to 1.15 multiplier
  const delay = Math.min(initialDelay * Math.pow(multiplier, attempt) * jitter, maxDelay);
  return Math.round(delay);
}

export function useWebSocket(
  endpoint: string,
  options: UseWebSocketOptions = {}
) {
  const {
    onMessage,
    onBatchedMessages,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    maxReconnectAttempts = 10,
    // Exponential backoff defaults
    initialReconnectDelay = 1000,  // Start at 1 second
    maxReconnectDelay = 30000,      // Max 30 seconds
    reconnectBackoffMultiplier = 2, // Double each time
    // Event batching defaults
    enableBatching = false,
    batchInterval = 100,            // Batch events every 100ms
    maxBatchSize = 50,              // Maximum events per batch
  } = options;

  const { data: session } = useSession();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Event batching state
  const batchedMessagesRef = useRef<WebSocketMessage[]>([]);
  const batchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  // Process batched messages
  const flushBatch = useCallback(() => {
    if (batchedMessagesRef.current.length > 0) {
      const batch = [...batchedMessagesRef.current];
      batchedMessagesRef.current = [];

      if (onBatchedMessages) {
        onBatchedMessages(batch);
      } else if (onMessage) {
        // If no batch handler, call individual handler for each message
        batch.forEach(msg => onMessage(msg));
      }
    }
    batchTimeoutRef.current = null;
  }, [onMessage, onBatchedMessages]);

  // Add message to batch or process immediately
  const processMessage = useCallback((message: WebSocketMessage) => {
    setLastMessage(message);

    if (enableBatching) {
      batchedMessagesRef.current.push(message);

      // Flush if batch is full
      if (batchedMessagesRef.current.length >= maxBatchSize) {
        if (batchTimeoutRef.current) {
          clearTimeout(batchTimeoutRef.current);
        }
        flushBatch();
      } else if (!batchTimeoutRef.current) {
        // Start batch timer if not already running
        batchTimeoutRef.current = setTimeout(flushBatch, batchInterval);
      }
    } else {
      // No batching - process immediately
      onMessage?.(message);
    }
  }, [enableBatching, maxBatchSize, batchInterval, flushBatch, onMessage]);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

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

    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
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
        console.log('[WebSocket] Connected to', url);
        setStatus('connected');
        reconnectAttemptsRef.current = 0;
        setReconnectAttempt(0);
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          processMessage(message);
        } catch {
          console.error('[WebSocket] Failed to parse message:', event.data);
        }
      };

      ws.onclose = (event) => {
        console.log('[WebSocket] Connection closed:', event.code, event.reason);
        setStatus('disconnected');
        wsRef.current = null;
        onDisconnect?.();

        // Flush any remaining batched messages
        if (enableBatching && batchedMessagesRef.current.length > 0) {
          flushBatch();
        }

        // Attempt reconnection with exponential backoff
        if (
          autoReconnect &&
          reconnectAttemptsRef.current < maxReconnectAttempts
        ) {
          const attempt = reconnectAttemptsRef.current;
          const delay = calculateBackoffDelay(
            attempt,
            initialReconnectDelay,
            maxReconnectDelay,
            reconnectBackoffMultiplier
          );

          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${attempt + 1}/${maxReconnectAttempts})`);

          setStatus('reconnecting');
          reconnectAttemptsRef.current += 1;
          setReconnectAttempt(attempt + 1);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('[WebSocket] Max reconnection attempts reached');
          setStatus('error');
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setStatus('error');
        onError?.(error);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      setStatus('error');
    }
  }, [
    endpoint,
    session?.accessToken,
    autoReconnect,
    maxReconnectAttempts,
    initialReconnectDelay,
    maxReconnectDelay,
    reconnectBackoffMultiplier,
    enableBatching,
    onConnect,
    onDisconnect,
    onError,
    processMessage,
    flushBatch,
  ]);

  const disconnect = useCallback(() => {
    clearReconnectTimeout();

    // Clear any pending batch
    if (batchTimeoutRef.current) {
      clearTimeout(batchTimeoutRef.current);
      batchTimeoutRef.current = null;
    }
    batchedMessagesRef.current = [];

    // Reset reconnection state
    reconnectAttemptsRef.current = 0;
    setReconnectAttempt(0);

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, [clearReconnectTimeout]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
      return true;
    }
    console.warn('[WebSocket] Cannot send message - not connected');
    return false;
  }, []);

  const subscribe = useCallback(
    (ticker: string) => {
      return send({ action: 'subscribe', ticker });
    },
    [send]
  );

  const unsubscribe = useCallback(
    (ticker: string) => {
      return send({ action: 'unsubscribe', ticker });
    },
    [send]
  );

  // Manual reconnect function (resets attempt counter)
  const reconnect = useCallback(() => {
    clearReconnectTimeout();
    reconnectAttemptsRef.current = 0;
    setReconnectAttempt(0);

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Small delay before reconnecting
    setTimeout(() => {
      connect();
    }, 100);
  }, [connect, clearReconnectTimeout]);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    status,
    lastMessage,
    reconnectAttempt,
    maxReconnectAttempts,
    send,
    subscribe,
    unsubscribe,
    connect,
    disconnect,
    reconnect,
  };
}
