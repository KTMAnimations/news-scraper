'use client';

import { useCallback, useEffect } from 'react';
import { useWebSocket, type WebSocketMessage } from './useWebSocket';
import { useEventStore } from '@/store/eventStore';
import type { Event } from '@/types/events';

interface EventMessage {
  type: 'event' | 'high_alpha' | 'ticker_event' | 'subscribed' | 'unsubscribed' | 'pong';
  data?: Event;
  ticker?: string;
}

interface UseEventStreamOptions {
  channel?: 'all' | 'high-alpha' | 'watchlist';
  ticker?: string;
  onNewEvent?: (event: Event) => void;
}

export function useEventStream(options: UseEventStreamOptions = {}) {
  const { channel = 'all', ticker, onNewEvent } = options;

  const addEvent = useEventStore((state) => state.addEvent);
  const addHighAlphaEvent = useEventStore((state) => state.addHighAlphaEvent);

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
    subscribe,
    unsubscribe,
    send,
  } = useWebSocket(endpoint, {
    onMessage: handleMessage,
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
    subscribe,
    unsubscribe,
  };
}
