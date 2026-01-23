import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { WatchlistItem } from '@/types/user';

interface WatchlistState {
  // Watchlist items (cached from API)
  items: WatchlistItem[];

  // Settings
  showWatchlistOnly: boolean;

  // Loading states
  isLoading: boolean;
  error: string | null;

  // Actions
  setItems: (items: WatchlistItem[]) => void;
  addItem: (item: WatchlistItem) => void;
  removeItem: (ticker: string) => void;
  isWatched: (ticker: string) => boolean;
  setShowWatchlistOnly: (value: boolean) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  getWatchedTickers: () => string[];
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      // Initial state
      items: [],
      showWatchlistOnly: false,
      isLoading: false,
      error: null,

      // Actions
      setItems: (items) => set({ items }),

      addItem: (item) => {
        const { items } = get();
        // Avoid duplicates
        if (items.some((i) => i.ticker === item.ticker)) return;
        set({ items: [item, ...items] });
      },

      removeItem: (ticker) => {
        const { items } = get();
        set({ items: items.filter((i) => i.ticker !== ticker) });
      },

      isWatched: (ticker) => {
        const { items } = get();
        return items.some((i) => i.ticker === ticker);
      },

      setShowWatchlistOnly: (value) => set({ showWatchlistOnly: value }),

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),

      getWatchedTickers: () => {
        const { items } = get();
        return items.map((i) => i.ticker);
      },
    }),
    {
      name: 'watchlist-settings',
      // Only persist settings, not the actual items (those come from API)
      partialize: (state) => ({ showWatchlistOnly: state.showWatchlistOnly }),
    }
  )
);

// Selector hooks for common access patterns
export const useWatchlistItems = () => useWatchlistStore((state) => state.items);
export const useShowWatchlistOnly = () => useWatchlistStore((state) => state.showWatchlistOnly);
export const useIsWatched = (ticker: string) => useWatchlistStore((state) => state.isWatched(ticker));
