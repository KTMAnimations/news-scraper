'use client';

import { useState, useEffect } from 'react';
import { Bell, BellOff, X } from 'lucide-react';
import { useNotifications } from '@/contexts/NotificationContext';
import { cn } from '@/lib/utils';

interface NotificationPermissionBannerProps {
  className?: string;
}

/**
 * Banner component that prompts users to enable push notifications.
 * Only shows when:
 * - Push notifications are supported
 * - Permission is not yet granted
 * - User hasn't dismissed the banner
 */
export function NotificationPermissionBanner({ className }: NotificationPermissionBannerProps) {
  const { isSupported, permission, isLoading, requestPermission } = useNotifications();
  const [isDismissed, setIsDismissed] = useState(false);
  const [isRequesting, setIsRequesting] = useState(false);

  // Check localStorage for dismissed state
  useEffect(() => {
    const dismissed = localStorage.getItem('notificationBannerDismissed');
    if (dismissed === 'true') {
      setIsDismissed(true);
    }
  }, []);

  // Don't show if:
  // - Not supported
  // - Already granted
  // - Dismissed by user
  // - Still loading
  if (!isSupported || permission === 'granted' || isDismissed || isLoading) {
    return null;
  }

  const handleEnable = async () => {
    setIsRequesting(true);
    try {
      await requestPermission();
    } finally {
      setIsRequesting(false);
    }
  };

  const handleDismiss = () => {
    setIsDismissed(true);
    localStorage.setItem('notificationBannerDismissed', 'true');
  };

  // Show different message if permission was denied
  if (permission === 'denied') {
    return (
      <div
        className={cn(
          'flex items-center justify-between gap-4 px-4 py-3 bg-warning-subtle border-b border-warning/30',
          className
        )}
      >
        <div className="flex items-center gap-3">
          <BellOff className="h-5 w-5 text-warning shrink-0" />
          <div>
            <p className="text-sm font-medium text-text-primary">
              Notifications are blocked
            </p>
            <p className="text-xs text-text-secondary">
              Enable notifications in your browser settings to receive real-time alerts.
            </p>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="p-1 text-text-tertiary hover:text-text-primary transition-colors"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-4 px-4 py-3 bg-accent-subtle border-b border-accent/30',
        className
      )}
    >
      <div className="flex items-center gap-3">
        <Bell className="h-5 w-5 text-accent shrink-0" />
        <div>
          <p className="text-sm font-medium text-text-primary">
            Enable push notifications
          </p>
          <p className="text-xs text-text-secondary">
            Get instant alerts for high-alpha signals and triggered alerts.
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={handleDismiss}
          className="px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors"
        >
          Not now
        </button>
        <button
          onClick={handleEnable}
          disabled={isRequesting}
          className="px-3 py-1.5 text-xs font-medium bg-accent text-bg-primary rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {isRequesting ? 'Enabling...' : 'Enable'}
        </button>
      </div>
    </div>
  );
}
