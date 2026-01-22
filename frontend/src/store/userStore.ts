import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, WatchlistItem, Alert } from '@/types/user';

interface UserState {
  // User data
  user: User | null;
  watchlist: WatchlistItem[];
  alerts: Alert[];

  // UI state
  isWatchlistExpanded: boolean;

  // Actions
  setUser: (user: User | null) => void;
  setWatchlist: (items: WatchlistItem[]) => void;
  addToWatchlist: (item: WatchlistItem) => void;
  removeFromWatchlist: (ticker: string) => void;
  setAlerts: (alerts: Alert[]) => void;
  addAlert: (alert: Alert) => void;
  updateAlert: (id: string, data: Partial<Alert>) => void;
  removeAlert: (id: string) => void;
  toggleWatchlistExpanded: () => void;
  reset: () => void;
}

const initialState = {
  user: null,
  watchlist: [],
  alerts: [],
  isWatchlistExpanded: true,
};

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      ...initialState,

      setUser: (user) => set({ user }),

      setWatchlist: (watchlist) => set({ watchlist }),

      addToWatchlist: (item) =>
        set((state) => ({
          watchlist: [...state.watchlist, item],
        })),

      removeFromWatchlist: (ticker) =>
        set((state) => ({
          watchlist: state.watchlist.filter((w) => w.ticker !== ticker),
        })),

      setAlerts: (alerts) => set({ alerts }),

      addAlert: (alert) =>
        set((state) => ({
          alerts: [...state.alerts, alert],
        })),

      updateAlert: (id, data) =>
        set((state) => ({
          alerts: state.alerts.map((a) =>
            a.id === id ? { ...a, ...data } : a
          ),
        })),

      removeAlert: (id) =>
        set((state) => ({
          alerts: state.alerts.filter((a) => a.id !== id),
        })),

      toggleWatchlistExpanded: () =>
        set((state) => ({
          isWatchlistExpanded: !state.isWatchlistExpanded,
        })),

      reset: () => set(initialState),
    }),
    {
      name: 'user-store',
      partialize: (state) => ({
        isWatchlistExpanded: state.isWatchlistExpanded,
      }),
    }
  )
);

// Selector hooks
export const useUser = () => useUserStore((state) => state.user);
export const useWatchlist = () => useUserStore((state) => state.watchlist);
export const useAlerts = () => useUserStore((state) => state.alerts);
export const useIsWatchlistExpanded = () =>
  useUserStore((state) => state.isWatchlistExpanded);
