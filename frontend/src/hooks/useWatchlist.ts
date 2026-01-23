import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useWatchlistStore } from '@/store/watchlistStore';
import type { WatchlistItem } from '@/types/user';

export function useWatchlist() {
  const queryClient = useQueryClient();
  const { setItems, addItem, removeItem, items, isWatched } = useWatchlistStore();

  // Fetch watchlist from API
  const {
    data: watchlistData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => api.getWatchlist(),
    staleTime: 30000, // 30 seconds
  });

  // Sync API data with store
  useEffect(() => {
    if (watchlistData) {
      setItems(watchlistData);
    }
  }, [watchlistData, setItems]);

  // Add to watchlist mutation
  const addMutation = useMutation({
    mutationFn: ({ ticker, notes }: { ticker: string; notes?: string }) =>
      api.addToWatchlist(ticker, notes),
    onSuccess: (newItem) => {
      addItem(newItem);
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });

  // Remove from watchlist mutation
  const removeMutation = useMutation({
    mutationFn: (ticker: string) => api.removeFromWatchlist(ticker),
    onSuccess: (_, ticker) => {
      removeItem(ticker);
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });

  // Toggle watchlist status
  const toggleWatchlist = (ticker: string, notes?: string) => {
    if (isWatched(ticker)) {
      removeMutation.mutate(ticker);
    } else {
      addMutation.mutate({ ticker, notes });
    }
  };

  return {
    items: watchlistData || items,
    isLoading,
    error: error?.message || null,
    refetch,
    addToWatchlist: (ticker: string, notes?: string) =>
      addMutation.mutate({ ticker, notes }),
    removeFromWatchlist: (ticker: string) => removeMutation.mutate(ticker),
    toggleWatchlist,
    isWatched,
    isAdding: addMutation.isPending,
    isRemoving: removeMutation.isPending,
  };
}

// Hook for checking if a specific ticker is watched
export function useIsTickerWatched(ticker: string): boolean {
  const { data: watchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => api.getWatchlist(),
    staleTime: 30000,
  });

  return watchlist?.some((item: WatchlistItem) => item.ticker === ticker) || false;
}
