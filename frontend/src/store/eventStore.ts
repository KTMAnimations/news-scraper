import { create } from 'zustand';
import type { Event, EventFilters } from '@/types/events';

const MAX_EVENTS = 500; // Maximum events to keep in memory

interface EventState {
  // Events
  events: Event[];
  highAlphaEvents: Event[];
  selectedEvent: Event | null;

  // Filters
  filters: EventFilters;

  // Loading states
  isLoading: boolean;
  error: string | null;

  // Actions
  setEvents: (events: Event[]) => void;
  addEvent: (event: Event) => void;
  addHighAlphaEvent: (event: Event) => void;
  selectEvent: (event: Event | null) => void;
  setFilters: (filters: Partial<EventFilters>) => void;
  clearFilters: () => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  clearEvents: () => void;
}

export const useEventStore = create<EventState>((set, get) => ({
  // Initial state
  events: [],
  highAlphaEvents: [],
  selectedEvent: null,
  filters: {},
  isLoading: false,
  error: null,

  // Actions
  setEvents: (events) => set({ events }),

  addEvent: (event) => {
    const { events, filters } = get();

    // Check if event matches current filters
    if (filters.ticker && event.ticker !== filters.ticker) return;
    if (filters.event_type && event.event_type !== filters.event_type) return;
    if (
      filters.sentiment_label &&
      event.sentiment_label !== filters.sentiment_label
    )
      return;
    if (filters.direction && event.direction !== filters.direction) return;
    if (
      filters.min_alpha_score &&
      (event.alpha_score === undefined ||
        event.alpha_score < filters.min_alpha_score)
    )
      return;

    // Add event to beginning of list
    const newEvents = [event, ...events];

    // Trim if exceeds max
    if (newEvents.length > MAX_EVENTS) {
      newEvents.pop();
    }

    set({ events: newEvents });
  },

  addHighAlphaEvent: (event) => {
    const { highAlphaEvents } = get();

    // Only add if alpha score is significant
    if (event.alpha_score === undefined || Math.abs(event.alpha_score) < 0.5) {
      return;
    }

    // Add to beginning
    const newEvents = [event, ...highAlphaEvents];

    // Keep only last 100 high alpha events
    if (newEvents.length > 100) {
      newEvents.pop();
    }

    set({ highAlphaEvents: newEvents });
  },

  selectEvent: (event) => set({ selectedEvent: event }),

  setFilters: (newFilters) =>
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
    })),

  clearFilters: () => set({ filters: {} }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  clearEvents: () =>
    set({
      events: [],
      highAlphaEvents: [],
      selectedEvent: null,
    }),
}));

// Selector hooks for common access patterns
export const useEvents = () => useEventStore((state) => state.events);
export const useHighAlphaEvents = () =>
  useEventStore((state) => state.highAlphaEvents);
export const useSelectedEvent = () =>
  useEventStore((state) => state.selectedEvent);
export const useEventFilters = () => useEventStore((state) => state.filters);
