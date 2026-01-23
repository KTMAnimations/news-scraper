'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import {
  isPushNotificationSupported,
  getNotificationPermissionStatus,
  requestNotificationPermission,
  getFCMToken,
  onForegroundMessage,
  showLocalNotification,
  AppNotificationPayload,
} from '@/lib/firebase';
import { api } from '@/lib/api';

/**
 * Notification preferences stored in the user's settings.
 */
export interface NotificationPreferences {
  // Push notification settings
  pushEnabled: boolean;
  realtimeAlerts: boolean;
  highAlphaSignals: boolean;
  // Email notification settings
  emailAlerts: boolean;
  dailyDigest: boolean;
  weeklyReport: boolean;
  productUpdates: boolean;
  // Thresholds
  minAlphaScore: number;
}

/**
 * Default notification preferences.
 */
const defaultPreferences: NotificationPreferences = {
  pushEnabled: true,
  realtimeAlerts: true,
  highAlphaSignals: true,
  emailAlerts: true,
  dailyDigest: true,
  weeklyReport: false,
  productUpdates: false,
  minAlphaScore: 0.7,
};

/**
 * Context value for notification management.
 */
interface NotificationContextValue {
  // Permission status
  isSupported: boolean;
  permission: NotificationPermission | 'unsupported';
  fcmToken: string | null;
  isLoading: boolean;
  error: string | null;

  // Preferences
  preferences: NotificationPreferences;
  updatePreferences: (updates: Partial<NotificationPreferences>) => Promise<void>;

  // Actions
  requestPermission: () => Promise<boolean>;
  registerToken: () => Promise<boolean>;
  unregisterToken: () => Promise<boolean>;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

/**
 * Hook to access notification context.
 */
export function useNotifications(): NotificationContextValue {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}

/**
 * Props for the NotificationProvider component.
 */
interface NotificationProviderProps {
  children: React.ReactNode;
}

/**
 * Provider component for notification management.
 */
export function NotificationProvider({ children }: NotificationProviderProps) {
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>('unsupported');
  const [fcmToken, setFcmToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [preferences, setPreferences] = useState<NotificationPreferences>(defaultPreferences);

  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Initialize notification state
  useEffect(() => {
    const initializeNotifications = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Check browser support
        const supported = isPushNotificationSupported();
        setIsSupported(supported);

        if (!supported) {
          setPermission('unsupported');
          setIsLoading(false);
          return;
        }

        // Get current permission status
        const currentPermission = getNotificationPermissionStatus();
        setPermission(currentPermission);

        // Load preferences from localStorage
        const savedPrefs = localStorage.getItem('notificationPreferences');
        if (savedPrefs) {
          try {
            setPreferences(JSON.parse(savedPrefs));
          } catch {
            console.warn('Failed to parse saved notification preferences');
          }
        }

        // If permission is granted, get FCM token
        if (currentPermission === 'granted') {
          const token = await getFCMToken();
          if (token) {
            setFcmToken(token);
            // Register token with backend
            await registerTokenWithBackend(token);
          }

          // Subscribe to foreground messages
          const unsubscribe = onForegroundMessage(handleForegroundMessage);
          if (unsubscribe) {
            unsubscribeRef.current = unsubscribe;
          }
        }
      } catch (err) {
        console.error('Error initializing notifications:', err);
        setError(err instanceof Error ? err.message : 'Failed to initialize notifications');
      } finally {
        setIsLoading(false);
      }
    };

    initializeNotifications();

    // Cleanup on unmount
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
    };
  }, []);

  /**
   * Handle foreground messages by showing a toast and local notification.
   */
  const handleForegroundMessage = useCallback((payload: { notification?: { title?: string; body?: string }; data?: Record<string, string> }) => {
    const notificationPayload: AppNotificationPayload = {
      title: payload.notification?.title || payload.data?.title || 'New Notification',
      body: payload.notification?.body || payload.data?.body || '',
      data: payload.data as AppNotificationPayload['data'],
    };

    // Show toast notification
    toast(notificationPayload.title, {
      description: notificationPayload.body,
      action: notificationPayload.data?.url
        ? {
            label: 'View',
            onClick: () => {
              if (notificationPayload.data?.url) {
                window.location.href = notificationPayload.data.url;
              }
            },
          }
        : undefined,
    });

    // Also show a local notification if in background
    if (document.hidden && preferences.pushEnabled) {
      showLocalNotification(notificationPayload);
    }
  }, [preferences.pushEnabled]);

  /**
   * Register FCM token with the backend.
   */
  const registerTokenWithBackend = async (token: string): Promise<boolean> => {
    try {
      await api.registerFCMToken(token);
      return true;
    } catch (err) {
      console.error('Failed to register FCM token with backend:', err);
      return false;
    }
  };

  /**
   * Unregister FCM token from the backend.
   */
  const unregisterTokenFromBackend = async (token: string): Promise<boolean> => {
    try {
      await api.unregisterFCMToken(token);
      return true;
    } catch (err) {
      console.error('Failed to unregister FCM token from backend:', err);
      return false;
    }
  };

  /**
   * Request notification permission from the user.
   */
  const requestPermission = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await requestNotificationPermission();
      setPermission(result);

      if (result === 'granted') {
        // Get FCM token
        const token = await getFCMToken();
        if (token) {
          setFcmToken(token);
          await registerTokenWithBackend(token);

          // Subscribe to foreground messages
          if (!unsubscribeRef.current) {
            const unsubscribe = onForegroundMessage(handleForegroundMessage);
            if (unsubscribe) {
              unsubscribeRef.current = unsubscribe;
            }
          }
        }
        return true;
      }

      return false;
    } catch (err) {
      console.error('Error requesting notification permission:', err);
      setError(err instanceof Error ? err.message : 'Failed to request permission');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported, handleForegroundMessage]);

  /**
   * Register FCM token manually (e.g., after login).
   */
  const registerToken = useCallback(async (): Promise<boolean> => {
    if (!isSupported || permission !== 'granted') {
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const token = await getFCMToken();
      if (token) {
        setFcmToken(token);
        return await registerTokenWithBackend(token);
      }
      return false;
    } catch (err) {
      console.error('Error registering FCM token:', err);
      setError(err instanceof Error ? err.message : 'Failed to register token');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported, permission]);

  /**
   * Unregister FCM token (e.g., on logout).
   */
  const unregisterToken = useCallback(async (): Promise<boolean> => {
    if (!fcmToken) {
      return true;
    }

    setIsLoading(true);
    setError(null);

    try {
      const success = await unregisterTokenFromBackend(fcmToken);
      if (success) {
        setFcmToken(null);
      }
      return success;
    } catch (err) {
      console.error('Error unregistering FCM token:', err);
      setError(err instanceof Error ? err.message : 'Failed to unregister token');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [fcmToken]);

  /**
   * Update notification preferences.
   */
  const updatePreferences = useCallback(async (updates: Partial<NotificationPreferences>): Promise<void> => {
    const newPreferences = { ...preferences, ...updates };
    setPreferences(newPreferences);

    // Save to localStorage
    localStorage.setItem('notificationPreferences', JSON.stringify(newPreferences));

    // Sync with backend
    try {
      await api.updateNotificationPreferences(newPreferences);
    } catch (err) {
      console.error('Failed to sync notification preferences with backend:', err);
      // Don't throw - local preferences are still updated
    }
  }, [preferences]);

  const contextValue: NotificationContextValue = {
    isSupported,
    permission,
    fcmToken,
    isLoading,
    error,
    preferences,
    updatePreferences,
    requestPermission,
    registerToken,
    unregisterToken,
  };

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
    </NotificationContext.Provider>
  );
}
