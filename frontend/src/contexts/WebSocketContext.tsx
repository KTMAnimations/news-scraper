'use client';

import React, { createContext, useContext, useCallback, useMemo } from 'react';
import { useWebSocket, WebSocketStatus, WebSocketMessage } from '@/hooks/useWebSocket';
import { useEventStore } from '@/store/eventStore';
import type { Event } from '@/types/events';

interface WebSocketContextValue {
  // Connection state
  status: WebSocketStatus;
  reconnectAttempt: number;
  maxReconnectAttempts: number;

  // Actions
  send: (data: unknown) => boolean;
  subscribe: (ticker: string) => boolean;
  unsubscribe: (ticker: string) => boolean;
  reconnect: () => void;
  disconnect: () => void;

  // Last received message
  lastMessage: WebSocketMessage | null;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface EventMessage {
  type: 'event' | 'high_alpha' | 'ticker_event' | 'subscribed' | 'unsubscribed' | 'pong' | 'connected' | 'error';
  data?: Event;
  ticker?: string;
  message?: string;
}

interface WebSocketProviderProps {
  children: React.ReactNode;
  // Optional endpoint override (defaults to /ws/events)
  endpoint?: string;
  // Enable batching to prevent UI thrashing
  enableBatching?: boolean;
  batchInterval?: number;
}

export function WebSocketProvider({
  children,
  endpoint = '/ws/events',
  enableBatching = true,
  batchInterval = 100,
}: WebSocketProviderProps) {
  const addEvent = useEventStore((state) => state.addEvent);
  const addHighAlphaEvent = useEventStore((state) => state.addHighAlphaEvent);

  // Handle a batch of messages at once to prevent UI thrashing
  const handleBatchedMessages = useCallback(
    (messages: WebSocketMessage[]) => {
      // Process all messages in the batch
      messages.forEach((message) => {
        const eventMessage = message as EventMessage;

        if (eventMessage.type === 'event' && eventMessage.data) {
          addEvent(eventMessage.data);
        } else if (eventMessage.type === 'high_alpha' && eventMessage.data) {
          addHighAlphaEvent(eventMessage.data);
        } else if (eventMessage.type === 'ticker_event' && eventMessage.data) {
          addEvent(eventMessage.data);
        }
      });
    },
    [addEvent, addHighAlphaEvent]
  );

  // Handle individual messages when batching is disabled
  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      const eventMessage = message as EventMessage;

      if (eventMessage.type === 'event' && eventMessage.data) {
        addEvent(eventMessage.data);
      } else if (eventMessage.type === 'high_alpha' && eventMessage.data) {
        addHighAlphaEvent(eventMessage.data);
      } else if (eventMessage.type === 'ticker_event' && eventMessage.data) {
        addEvent(eventMessage.data);
      }
    },
    [addEvent, addHighAlphaEvent]
  );

  const {
    status,
    lastMessage,
    reconnectAttempt,
    maxReconnectAttempts,
    send,
    subscribe,
    unsubscribe,
    reconnect,
    disconnect,
  } = useWebSocket(endpoint, {
    enableBatching,
    batchInterval,
    onMessage: enableBatching ? undefined : handleMessage,
    onBatchedMessages: enableBatching ? handleBatchedMessages : undefined,
    onConnect: () => {
      console.log('[WebSocketContext] Connected to event stream');
    },
    onDisconnect: () => {
      console.log('[WebSocketContext] Disconnected from event stream');
    },
  });

  const value = useMemo<WebSocketContextValue>(
    () => ({
      status,
      reconnectAttempt,
      maxReconnectAttempts,
      send,
      subscribe,
      unsubscribe,
      reconnect,
      disconnect,
      lastMessage,
    }),
    [
      status,
      reconnectAttempt,
      maxReconnectAttempts,
      send,
      subscribe,
      unsubscribe,
      reconnect,
      disconnect,
      lastMessage,
    ]
  );

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
}

// Convenience hook for just the status
export function useConnectionStatus() {
  const context = useContext(WebSocketContext);
  if (!context) {
    // Return a default disconnected status if not within provider
    return {
      status: 'disconnected' as WebSocketStatus,
      reconnectAttempt: 0,
      maxReconnectAttempts: 10,
      reconnect: () => {},
    };
  }
  return {
    status: context.status,
    reconnectAttempt: context.reconnectAttempt,
    maxReconnectAttempts: context.maxReconnectAttempts,
    reconnect: context.reconnect,
  };
}
