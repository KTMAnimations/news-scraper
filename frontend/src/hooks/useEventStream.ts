'use client';

import { useCallback, useEffect } from 'react';
import { useWebSocket, type WebSocketMessage } from './useWebSocket';
import { useEventStore } from '@/store/eventStore';
import type { Event } from '@/types/events';

interface EventMessage {
  type: 'event' | 'high_alpha' | 'ticker_event' | 'subscribed' | 'unsubscribed' | 'pong' | 'connected' | 'error';
  data?: Event;
  ticker?: string;
  message?: string;
}

interface UseEventStreamOptions {
  channel?: 'all' | 'high-alpha' | 'watchlist';
  ticker?: string;
  onNewEvent?: (event: Event) => void;
  onNewEvents?: (events: Event[]) => void;
  // Enable batching to prevent UI thrashing when receiving many events
  enableBatching?: boolean;
  batchInterval?: number;
}

export function useEventStream(options: UseEventStreamOptions = {}) {
  const {
    channel = 'all',
    ticker,
    onNewEvent,
    onNewEvents,
    enableBatching = true,
    batchInterval = 100,
  } = options;

  const addEvent = useEventStore((state) => state.addEvent);
  const addHighAlphaEvent = useEventStore((state) => state.addHighAlphaEvent);

  // Handle batched messages to prevent UI thrashing
  const handleBatchedMessages = useCallback(
    (messages: WebSocketMessage[]) => {
      const newEvents: Event[] = [];

      messages.forEach((message) => {
        const eventMessage = message as EventMessage;

        if (eventMessage.type === 'event' && eventMessage.data) {
          addEvent(eventMessage.data);
          newEvents.push(eventMessage.data);
        } else if (eventMessage.type === 'high_alpha' && eventMessage.data) {
          addHighAlphaEvent(eventMessage.data);
          newEvents.push(eventMessage.data);
        } else if (eventMessage.type === 'ticker_event' && eventMessage.data) {
          addEvent(eventMessage.data);
          newEvents.push(eventMessage.data);
        }
      });

      // Call batch callback if provided
      if (onNewEvents && newEvents.length > 0) {
        onNewEvents(newEvents);
      }

      // Also call individual callback for each event if provided (backwards compatible)
      if (onNewEvent) {
        newEvents.forEach((event) => onNewEvent(event));
      }
    },
    [addEvent, addHighAlphaEvent, onNewEvent, onNewEvents]
  );

  // Handle individual messages (when batching is disabled)
  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      const eventMessage = message as EventMessage;

      if (eventMessage.type === 'event' && eventMessage.data) {
        addEvent(eventMessage.data);
        onNewEvent?.(eventMessage.data);
      } else if (eventMessage.type === 'high_alpha' && eventMessage.data) {
        addHighAlphaEvent(eventMessage.data);
        onNewEvent?.(eventMessage.data);
      } else if (eventMessage.type === 'ticker_event' && eventMessage.data) {
        addEvent(eventMessage.data);
        onNewEvent?.(eventMessage.data);
      }
    },
    [addEvent, addHighAlphaEvent, onNewEvent]
  );

  // Determine endpoint based on channel
  let endpoint = '/ws/events';
  if (channel === 'high-alpha') {
    endpoint = '/ws/events/high-alpha';
  } else if (channel === 'watchlist') {
    endpoint = '/ws/events/watchlist';
  } else if (ticker) {
    endpoint = `/ws/events/ticker/${ticker}`;
  }

  const {
    status,
    lastMessage,
    reconnectAttempt,
    maxReconnectAttempts,
    subscribe,
    unsubscribe,
    send,
    reconnect,
  } = useWebSocket(endpoint, {
    enableBatching,
    batchInterval,
    onMessage: enableBatching ? undefined : handleMessage,
    onBatchedMessages: enableBatching ? handleBatchedMessages : undefined,
  });

  // Ping to keep connection alive
  useEffect(() => {
    if (status !== 'connected') return;

    const pingInterval = setInterval(() => {
      send({ action: 'ping' });
    }, 30000); // Ping every 30 seconds

    return () => clearInterval(pingInterval);
  }, [status, send]);

  return {
    status,
    lastMessage,
    reconnectAttempt,
    maxReconnectAttempts,
    subscribe,
    unsubscribe,
    reconnect,
  };
}
