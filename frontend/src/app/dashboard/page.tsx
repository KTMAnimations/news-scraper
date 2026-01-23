'use client';

import { useEffect } from 'react';
import { useLatestEvents } from '@/hooks/useApi';
import { useEventStream } from '@/hooks/useEventStream';
import { useEventStore } from '@/store/eventStore';
import { CustomizableDashboard } from '@/components/dashboard/CustomizableDashboard';

export default function DashboardPage() {
  // Connect to WebSocket for real-time updates
  useEventStream({ channel: 'all' });

  const setEvents = useEventStore((state) => state.setEvents);

  // Fetch initial events using the custom hook with caching and retry logic
  const { data: initialEvents } = useLatestEvents(50);

  // Set initial events in the store
  useEffect(() => {
    if (initialEvents) {
      setEvents(initialEvents);
    }
  }, [initialEvents, setEvents]);

  return <CustomizableDashboard />;
}
