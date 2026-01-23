/**
 * Firebase Cloud Messaging initialization and utilities.
 *
 * Environment variables required:
 * - NEXT_PUBLIC_FIREBASE_API_KEY
 * - NEXT_PUBLIC_FIREBASE_PROJECT_ID
 * - NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID
 */

import { initializeApp, getApps, FirebaseApp } from 'firebase/app';
import {
  getMessaging,
  getToken,
  onMessage,
  Messaging,
  MessagePayload,
} from 'firebase/messaging';

// Firebase configuration from environment variables
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Initialize Firebase app (singleton)
let app: FirebaseApp | null = null;
let messaging: Messaging | null = null;

/**
 * Initialize Firebase app.
 * Only initializes once, returns existing instance on subsequent calls.
 */
export function initializeFirebase(): FirebaseApp | null {
  if (typeof window === 'undefined') {
    return null;
  }

  if (!firebaseConfig.apiKey || !firebaseConfig.projectId) {
    console.warn('Firebase configuration is incomplete. Push notifications will be disabled.');
    return null;
  }

  if (app) {
    return app;
  }

  const existingApps = getApps();
  if (existingApps.length > 0) {
    app = existingApps[0];
  } else {
    app = initializeApp(firebaseConfig);
  }

  return app;
}

/**
 * Get Firebase Messaging instance.
 * Initializes Firebase if not already done.
 */
export function getFirebaseMessaging(): Messaging | null {
  if (typeof window === 'undefined') {
    return null;
  }

  if (messaging) {
    return messaging;
  }

  const firebaseApp = initializeFirebase();
  if (!firebaseApp) {
    return null;
  }

  try {
    messaging = getMessaging(firebaseApp);
    return messaging;
  } catch (error) {
    console.error('Failed to initialize Firebase Messaging:', error);
    return null;
  }
}

/**
 * Check if the browser supports push notifications.
 */
export function isPushNotificationSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'Notification' in window &&
    'serviceWorker' in navigator &&
    'PushManager' in window
  );
}

/**
 * Get the current notification permission status.
 */
export function getNotificationPermissionStatus(): NotificationPermission | 'unsupported' {
  if (!isPushNotificationSupported()) {
    return 'unsupported';
  }
  return Notification.permission;
}

/**
 * Request notification permission from the user.
 * Returns the permission status after the request.
 */
export async function requestNotificationPermission(): Promise<NotificationPermission | 'unsupported'> {
  if (!isPushNotificationSupported()) {
    return 'unsupported';
  }

  try {
    const permission = await Notification.requestPermission();
    return permission;
  } catch (error) {
    console.error('Error requesting notification permission:', error);
    return 'denied';
  }
}

/**
 * Register the service worker for Firebase Cloud Messaging.
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js', {
      scope: '/',
    });
    console.log('Service Worker registered with scope:', registration.scope);
    return registration;
  } catch (error) {
    console.error('Service Worker registration failed:', error);
    return null;
  }
}

/**
 * Get the FCM token for the current device.
 * Requires notification permission and service worker registration.
 *
 * @param vapidKey - VAPID key for web push (optional, uses default if not provided)
 * @returns FCM token or null if unavailable
 */
export async function getFCMToken(vapidKey?: string): Promise<string | null> {
  const messagingInstance = getFirebaseMessaging();
  if (!messagingInstance) {
    console.warn('Firebase Messaging not available');
    return null;
  }

  // Check permission
  const permission = getNotificationPermissionStatus();
  if (permission !== 'granted') {
    console.warn('Notification permission not granted');
    return null;
  }

  // Ensure service worker is registered
  const swRegistration = await registerServiceWorker();
  if (!swRegistration) {
    console.warn('Service worker not registered');
    return null;
  }

  try {
    const token = await getToken(messagingInstance, {
      vapidKey: vapidKey || process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY,
      serviceWorkerRegistration: swRegistration,
    });

    if (token) {
      console.log('FCM Token obtained successfully');
      return token;
    } else {
      console.warn('No FCM token available');
      return null;
    }
  } catch (error) {
    console.error('Error getting FCM token:', error);
    return null;
  }
}

/**
 * Callback type for handling foreground messages.
 */
export type MessageHandler = (payload: MessagePayload) => void;

/**
 * Subscribe to foreground messages.
 * These are messages received when the app is in the foreground.
 *
 * @param handler - Callback function to handle incoming messages
 * @returns Unsubscribe function
 */
export function onForegroundMessage(handler: MessageHandler): (() => void) | null {
  const messagingInstance = getFirebaseMessaging();
  if (!messagingInstance) {
    return null;
  }

  return onMessage(messagingInstance, (payload) => {
    console.log('Foreground message received:', payload);
    handler(payload);
  });
}

/**
 * Notification payload structure for the application.
 */
export interface AppNotificationPayload {
  title: string;
  body: string;
  icon?: string;
  badge?: string;
  tag?: string;
  data?: {
    type: 'event' | 'alert' | 'digest' | 'system';
    eventId?: string;
    ticker?: string;
    alertId?: string;
    url?: string;
    [key: string]: unknown;
  };
}

/**
 * Display a local notification (used for foreground messages).
 */
export function showLocalNotification(payload: AppNotificationPayload): void {
  if (!isPushNotificationSupported() || Notification.permission !== 'granted') {
    return;
  }

  const notification = new Notification(payload.title, {
    body: payload.body,
    icon: payload.icon || '/icons/notification-icon.png',
    badge: payload.badge || '/icons/badge-icon.png',
    tag: payload.tag,
    data: payload.data,
  });

  notification.onclick = () => {
    window.focus();
    if (payload.data?.url) {
      window.location.href = payload.data.url;
    } else if (payload.data?.eventId) {
      window.location.href = `/dashboard/events/${payload.data.eventId}`;
    } else if (payload.data?.ticker) {
      window.location.href = `/dashboard/ticker/${payload.data.ticker}`;
    }
    notification.close();
  };
}
