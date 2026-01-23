/**
 * Firebase Cloud Messaging Service Worker
 *
 * This service worker handles push notifications when the app is in the background
 * or when the browser is closed.
 */

// Import Firebase scripts
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

// Firebase configuration
// Note: These values should match your Firebase project configuration
// They are safe to expose in client-side code
const firebaseConfig = {
  apiKey: self.FIREBASE_API_KEY || '',
  projectId: self.FIREBASE_PROJECT_ID || '',
  messagingSenderId: self.FIREBASE_MESSAGING_SENDER_ID || '',
  appId: self.FIREBASE_APP_ID || '',
};

// Initialize Firebase in the service worker
firebase.initializeApp(firebaseConfig);

// Get Firebase Messaging instance
const messaging = firebase.messaging();

/**
 * Handle background messages.
 * This is called when a message is received while the app is not in focus.
 */
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message:', payload);

  // Extract notification data
  const notificationTitle = payload.notification?.title || payload.data?.title || 'New Notification';
  const notificationBody = payload.notification?.body || payload.data?.body || '';
  const notificationIcon = payload.notification?.icon || payload.data?.icon || '/icons/notification-icon.png';
  const notificationBadge = payload.notification?.badge || payload.data?.badge || '/icons/badge-icon.png';

  // Build notification options
  const notificationOptions = {
    body: notificationBody,
    icon: notificationIcon,
    badge: notificationBadge,
    tag: payload.data?.tag || 'default',
    data: {
      ...payload.data,
      fcm_notification: true,
    },
    // Actions for the notification (if supported)
    actions: [],
    // Require interaction for important notifications
    requireInteraction: payload.data?.urgency === 'critical' || payload.data?.urgency === 'high',
    // Vibration pattern for mobile devices
    vibrate: [100, 50, 100],
    // Timestamp
    timestamp: Date.now(),
  };

  // Add actions based on notification type
  if (payload.data?.type === 'event' && payload.data?.ticker) {
    notificationOptions.actions = [
      {
        action: 'view-ticker',
        title: `View ${payload.data.ticker}`,
      },
      {
        action: 'dismiss',
        title: 'Dismiss',
      },
    ];
  } else if (payload.data?.type === 'alert') {
    notificationOptions.actions = [
      {
        action: 'view-alert',
        title: 'View Alert',
      },
      {
        action: 'dismiss',
        title: 'Dismiss',
      },
    ];
  }

  // Show the notification
  return self.registration.showNotification(notificationTitle, notificationOptions);
});

/**
 * Handle notification click events.
 */
self.addEventListener('notificationclick', (event) => {
  console.log('[firebase-messaging-sw.js] Notification click:', event.action);

  event.notification.close();

  // Determine the URL to open based on the action and data
  let targetUrl = '/dashboard';

  const data = event.notification.data || {};

  if (event.action === 'view-ticker' && data.ticker) {
    targetUrl = `/dashboard/ticker/${data.ticker}`;
  } else if (event.action === 'view-alert' && data.alertId) {
    targetUrl = `/dashboard/alerts`;
  } else if (event.action === 'dismiss') {
    return; // Just close the notification
  } else if (data.url) {
    targetUrl = data.url;
  } else if (data.eventId) {
    targetUrl = `/dashboard/events/${data.eventId}`;
  } else if (data.ticker) {
    targetUrl = `/dashboard/ticker/${data.ticker}`;
  }

  // Open or focus the appropriate window
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Check if there's already a window open
      for (const client of clientList) {
        if (client.url.includes('/dashboard') && 'focus' in client) {
          client.focus();
          client.postMessage({
            type: 'NOTIFICATION_CLICK',
            data: data,
            targetUrl: targetUrl,
          });
          return;
        }
      }
      // If no window is open, open a new one
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

/**
 * Handle notification close events.
 */
self.addEventListener('notificationclose', (event) => {
  console.log('[firebase-messaging-sw.js] Notification closed:', event.notification.tag);
});

/**
 * Handle service worker installation.
 */
self.addEventListener('install', (event) => {
  console.log('[firebase-messaging-sw.js] Service Worker installing.');
  self.skipWaiting();
});

/**
 * Handle service worker activation.
 */
self.addEventListener('activate', (event) => {
  console.log('[firebase-messaging-sw.js] Service Worker activated.');
  event.waitUntil(clients.claim());
});

/**
 * Handle messages from the main thread.
 */
self.addEventListener('message', (event) => {
  console.log('[firebase-messaging-sw.js] Message received:', event.data);

  if (event.data && event.data.type === 'FIREBASE_CONFIG') {
    // Update Firebase config if needed
    console.log('[firebase-messaging-sw.js] Firebase config received');
  }
});
