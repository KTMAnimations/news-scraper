'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionProvider } from 'next-auth/react';
import { useState } from 'react';
import { Toaster } from 'sonner';
import { WebSocketProvider } from '@/contexts/WebSocketContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { InstallPrompt } from '@/components/pwa/InstallPrompt';
import { ApiError } from '@/lib/api';

/**
 * Determine if a failed request should be retried at the React Query level.
 * Note: The API client already handles retries with exponential backoff,
 * but this serves as an additional layer for React Query's built-in retry.
 */
function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  // Don't retry more than 3 times total
  if (failureCount >= 3) {
    return false;
  }

  // Don't retry client errors (4xx)
  if (error instanceof ApiError && error.isClientError()) {
    return false;
  }

  // Retry network errors and server errors
  return true;
}

/**
 * Calculate retry delay with exponential backoff
 * Returns delay in milliseconds: 1s, 2s, 4s
 */
function getRetryDelay(attemptIndex: number): number {
  return Math.min(1000 * Math.pow(2, attemptIndex), 8000);
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Default stale time - individual hooks override this with endpoint-specific times
            staleTime: 60 * 1000, // 1 minute

            // Garbage collection time - how long inactive data stays in cache
            gcTime: 5 * 60 * 1000, // 5 minutes

            // Retry configuration with exponential backoff
            retry: shouldRetryQuery,
            retryDelay: getRetryDelay,

            // Don't refetch on window focus by default (can be overridden per query)
            refetchOnWindowFocus: false,

            // Refetch on reconnect for stale data
            refetchOnReconnect: 'always',

            // Don't refetch on mount if data is fresh
            refetchOnMount: true,

            // Network mode - always try to fetch, even if offline (will use cache)
            networkMode: 'offlineFirst',
          },
          mutations: {
            // Retry mutations once for network errors only
            retry: (failureCount, error) => {
              if (failureCount >= 1) return false;
              if (error instanceof ApiError && error.isClientError()) return false;
              return true;
            },
            retryDelay: 1000,

            // Network mode for mutations
            networkMode: 'offlineFirst',
          },
        },
      })
  );

  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>
        <WebSocketProvider enableBatching={true} batchInterval={100}>
          <NotificationProvider>
            {children}
          </NotificationProvider>
        </WebSocketProvider>
        <Toaster position="top-right" richColors closeButton />
        <InstallPrompt />
      </QueryClientProvider>
    </SessionProvider>
  );
}
